from pathlib import Path
import os
import shutil
import glob
import json
from fuzzywuzzy import fuzz
from datetime import datetime
from typing import List
from pydantic import BaseModel, Field
import autogen
import memories.system_messages_JSON as system_messages
from autogen.agentchat.groupchat import GroupChat
from autogen.agentchat.agent import Agent
from autogen.agentchat.assistant_agent import AssistantAgent
from autogen.agentchat import UserProxyAgent
import matplotlib.pyplot as plt  # noqa E402
import networkx as nx  # noqa E402

now = datetime.now()
json_format = " Response must be in JSON format."

current_time = now.strftime("%Y:%m:%d:%H:%M:%S")
print("Current Time =", current_time)
print("Autogen Version =", autogen.__version__) 

# The default config list in notebook.
config_list_gpt4 = autogen.config_list_from_json(
    "D:\Github\Aretai-AGI\OAI_CONFIG_LIST",
            filter_dict={
            "model": ["gpt-4-turbo-preview"],
    },
)

config_list_text = autogen.config_list_from_json(
    "D:\Github\Aretai-AGI\OAI_CONFIG_LIST",
            filter_dict={
            "model": ["gpt-4-turbo-preview"],
    },
)

config_list_json = autogen.config_list_from_json(
    "D:\Github\Aretai-AGI\OAI_CONFIG_LIST",
            filter_dict={
            "model": ["gpt-4-0125-preview"],
    },
)



manager_config = {
    "timeout": 600,
    "cache_seed": 44,  # change the seed for different trials
    "config_list": autogen.config_list_from_json(
        "D:\Github\Aretai-AGI\OAI_CONFIG_LIST",
            filter_dict={
            "model": ["gpt-4-turbo-preview"]},
    ),
    "temperature": 0,
}


# llm config


llm_config = {"config_list": config_list_text, 
              "seed": 42
              }


# File operations agents
file_agents = []
file_speaker_transitions_dict = {}

def get_agent_of_name(file_agents, name) -> Agent:
    for agent in file_agents:
        if agent.name == name:
            return agent

file_agents.append(
    AssistantAgent(
        name="fileops_agent",
        system_message=system_messages.fileopsagent_systemmessage,
        llm_config=llm_config,
        human_input_mode="NEVER",
        description="""
        This Agent should be called by file_response_agent when there is a new incoming task.
        """,
        code_execution_config=False, #{"work_dir": "coding", "use_docker": False},
    )
)
file_speaker_transitions_dict[file_agents[-1]] = []

fileops_agent = file_agents[0]

file_agents.append(
    UserProxyAgent(
        name="fileops_proxy",
        llm_config=llm_config,
        description=""" DO NOT CALL THIS AGENT. Is is used for programatic function calling. Calling this agent results in infinite loops that achieve nothing.""",
        code_execution_config=False, #{"work_dir": "coding", "use_docker": False},
        human_input_mode="NEVER",
    )
)
file_speaker_transitions_dict[file_agents[-1]] = []

fileops_proxy = file_agents[1]



file_agents.append(
    AssistantAgent(
        name="file_response_agent",
        system_message=system_messages.fileagentresponse_systemmessage,
        llm_config=llm_config,
        human_input_mode="NEVER",
        description="""Call this Agent if: 

        The Fileops_agent should call this agent:
            IF all requested function calls have returned a result, then call this agent.
            IF the request_state is `TERMINUS`

        DO NOT CALL THIS AGENT IF:
            The fileops_agent is anwsering a complex query that takes multiple function calls, the multion_agent must be allowed to complete all the function calls, including a sensible number of retry attempts. 
            Do not engage this agent until the function calling process is complete.
        """
    )
)

file_speaker_transitions_dict[file_agents[-1]] = []

file_response_agent = file_agents[2]




def is_termination_msg(content) -> bool:
    have_content = content.get("content", None) is not None
    if have_content and "TERMINUS" in content["content"]:
        return True
    return False

file_agents.append(
    UserProxyAgent(
        name="fileops_userproxy",
        system_message="Terminator admin. Reply in JSON",
        code_execution_config=False,
        description=""" DO NOT CALL THIS AGENT. Is is used for programatic function calling. Calling this agent results in infinite loops that achieve nothing.""",
        is_termination_msg=is_termination_msg,
        human_input_mode="NEVER",
    )
)
file_speaker_transitions_dict[file_agents[-1]] = []

file_userproxy = file_agents[3]

# Speaker transitions
file_speaker_transitions_dict[get_agent_of_name(file_agents, "fileops_userproxy")].append(get_agent_of_name(file_agents, name="file_response_agent"))
file_speaker_transitions_dict[get_agent_of_name(file_agents, "file_response_agent")].append(get_agent_of_name(file_agents, name="fileops_agent"))
file_speaker_transitions_dict[get_agent_of_name(file_agents, "fileops_agent")].append(get_agent_of_name(file_agents, name="fileops_proxy"))
file_speaker_transitions_dict[get_agent_of_name(file_agents, "fileops_proxy")].append(get_agent_of_name(file_agents, name="fileops_agent"))
file_speaker_transitions_dict[get_agent_of_name(file_agents, "fileops_agent")].append(get_agent_of_name(file_agents, name="file_response_agent"))
file_speaker_transitions_dict[get_agent_of_name(file_agents, "file_response_agent")].append(get_agent_of_name(file_agents, name="fileops_userproxy"))

# File operation functions (read_file, check_directory, change_directory, search_files, perform_file_operation, perform_directory_operation)
# ...



############################################################################################################
# File Ops Functions
############################################################################################################



class ChangeDirectoryRequest(BaseModel):
    directory_path: str = Field(..., description="The path to the directory to change to.")


class DirectoryCheckRequest(BaseModel):
    directory_path: str = Field(..., description="The path to the directory to be checked.")


class DirectoryCheckResponse(BaseModel):
    directory_contents: List[str] = Field(..., description="The contents of the directory.")


class FileReadRequest(BaseModel):
    file_path: str = Field(..., description="The path to the file to be read.")


class FileReadResponse(BaseModel):
    file_contents: str = Field(..., description="The contents of the file.")


class ChangeDirectoryResponse(BaseModel):
    success: bool = Field(..., description="Indicates if the directory change was successful.")
    message: str = Field(..., description="Additional information about the directory change.")


class SearchFilesRequest(BaseModel):
    search_pattern: str = Field(..., description="The search pattern to match files.")


class SearchFilesResponse(BaseModel):
    matching_files: List[str] = Field(..., description="The list of files matching the search pattern.")


class FileOperationRequest(BaseModel):
    file_path: str = Field(..., description="The path to the file to perform the operation on.")
    operation: str = Field(..., description="The file operation to perform (create, copy).")
    destination_path: str = Field(None, description="The destination path for copy operations.")


class FileOperationResponse(BaseModel):
    success: bool = Field(..., description="Indicates if the file operation was successful.")
    message: str = Field(..., description="Additional information about the file operation.")


class DirectoryOperationRequest(BaseModel):
    directory_path: str = Field(..., description="The path to the directory to perform the operation on.")
    operation: str = Field(..., description="The directory operation to perform (create).")


class DirectoryOperationResponse(BaseModel):
    success: bool = Field(..., description="Indicates if the directory operation was successful.")
    message: str = Field(..., description="Additional information about the directory operation.")

class ListDirectoryRequest(BaseModel):
    directory_path: str = Field(..., description="The path to the directory to list contents.")

class ListDirectoryResponse(BaseModel):
    success: bool = Field(..., description="Indicates if listing the directory contents was successful.")
    contents: List[str] = Field(..., description="The list of files and directories in the specified directory.")
    message: str = Field(..., description="Additional information about the directory listing.")

class FileUpdateRequest(BaseModel):
    file_path: str = Field(..., description="The path to the file to be updated.")
    content: str = Field(..., description="The new content of the file.")

class FileUpdateResponse(BaseModel):
    success: bool = Field(..., description="Indicates if the file update was successful.")
    message: str = Field(..., description="Additional information about the file update.")


ALLOWED_PATHS = [
    "D:\Github\Aretai-AGI\agent_workspace",
    "D:\Github\Aretai-AGI\agent_workspace\playground",
    "D:\Github\Aretai-AGI\agent_workspace\playground\books",
    "D:\Github\Aretai-AGI\agent_workspace\playground\books\snow_crash",
    "agent_workspace",
    "agent_workspace/playground",
    "agent_workspace/playground/books",
    "agent_workspace/playground/books/snow_crash",
    "playground",
    "playground/books",
    "playground/books/snow_crash",
    "books",
    "books/snow_crash",
    "snow_crash"

    # Add more allowed paths as needed
]

PLAYGROUND_DIRECTORY = Path("playground")

def process_directory_path(directory_path: str) -> Path:
    return PLAYGROUND_DIRECTORY / Path(directory_path)

def check_directory_exists(directory_path: str) -> bool:
    full_path = process_directory_path(directory_path)
    return full_path.is_dir()

def validate_path(path: Path) -> bool:
    for allowed_path in ALLOWED_PATHS:
        try:
            path.relative_to(Path(allowed_path))
            return True
        except ValueError:
            pass
    return True

@fileops_proxy.register_for_execution()
@fileops_agent.register_for_llm(description="read_file")
def read_file(file_path: str) -> FileReadResponse:
    print(f"Current working directory: {os.getcwd()}")
    full_path = Path(file_path)
    if not validate_path(full_path):
        return FileReadResponse(file_contents=f"Access denied. File path is not in the allowed list: {file_path}")
    if not full_path.is_file():
        return FileReadResponse(file_contents=f"File not found: {file_path}")
    try:
        file_contents = full_path.read_text()
        return FileReadResponse(file_contents=file_contents)
    except Exception as e:
        return FileReadResponse(file_contents=f"Error reading file: {str(e)}")

@fileops_proxy.register_for_execution()
@fileops_agent.register_for_llm(description="check_directory")
def check_directory() -> DirectoryCheckResponse:
    current_directory = os.getcwd()
    try:
        directory_contents = [item.name for item in Path(current_directory).iterdir()]
        return DirectoryCheckResponse(directory_contents=directory_contents)
    except Exception as e:
        return DirectoryCheckResponse(directory_contents=[f"Error checking directory: {str(e)}"])

@fileops_proxy.register_for_execution()
@fileops_agent.register_for_llm(description="change_directory")
def change_directory(directory_path: str) -> ChangeDirectoryResponse:
    print(f"Current working directory: {os.getcwd()}")
    full_path = Path(directory_path)
    print(f"Full path: {full_path}")
    if not validate_path(full_path):
        return ChangeDirectoryResponse(success=False, message=f"Access denied. Directory is outside the playground: {directory_path}")
    if not full_path.is_dir():
        return ChangeDirectoryResponse(success=False, message=f"Directory not found: {directory_path}")
    try:
        os.chdir(full_path)
        return ChangeDirectoryResponse(success=True, message=f"Changed directory to {directory_path}")
    except Exception as e:
        return ChangeDirectoryResponse(success=False, message=f"Error changing directory: {str(e)}")
    
@fileops_proxy.register_for_execution()
@fileops_agent.register_for_llm(description="search_files")
def search_files(search_pattern: str) -> SearchFilesResponse:
    print(f"Current working directory: {os.getcwd()}")
    full_pattern = str(PLAYGROUND_DIRECTORY / "**" / "*")
    try:
        all_files = [str(Path(file).relative_to(PLAYGROUND_DIRECTORY)) for file in glob.glob(full_pattern, recursive=True)]
        matching_files = [
            file
            for file in all_files
            if validate_path(PLAYGROUND_DIRECTORY / file) and fuzz.partial_ratio(search_pattern, file) >= 50
        ]
        return SearchFilesResponse(matching_files=matching_files)
    except Exception as e:
        return SearchFilesResponse(matching_files=[f"Error searching files: {str(e)}"])

@fileops_proxy.register_for_execution()
@fileops_agent.register_for_llm(description="perform_file_operation")
def perform_file_operation(file_path: str, operation: str, content: str = None, destination_path: str = None) -> FileOperationResponse:
    print(f"Current working directory: {os.getcwd()}")
    full_path = PLAYGROUND_DIRECTORY / Path(file_path)
    print(f"Full path: {full_path}")
    if not validate_path(full_path) or (destination_path and not validate_path(process_directory_path(destination_path))):
        return FileOperationResponse(success=False, message=f"Access denied. File path is outside the playground: {file_path}")
    try:
        if operation == "create":
            full_path.write_text(content)
            return FileOperationResponse(success=True, message=f"File created: {file_path}")
        elif operation == "copy" and destination_path:
            full_destination_path = process_directory_path(destination_path)
            shutil.copy(full_path, full_destination_path)
            return FileOperationResponse(success=True, message=f"File copied from {file_path} to {destination_path}")
        else:
            return FileOperationResponse(success=False, message=f"Invalid file operation: {operation}")
    except Exception as e:
        return FileOperationResponse(success=False, message=f"Error performing file operation: {str(e)}")

@fileops_proxy.register_for_execution()
@fileops_agent.register_for_llm(description="perform_directory_operation")
def perform_directory_operation(directory_path: str, operation: str) -> DirectoryOperationResponse:
    print(f"Current working directory: {os.getcwd()}")
    full_path = PLAYGROUND_DIRECTORY / Path(directory_path)
    print(f"Full path: {directory_path}")
    if not validate_path(full_path):
        return DirectoryOperationResponse(success=False, message=f"Access denied. Directory path is outside the playground: {directory_path}")
    try:
        if operation == "create":
            full_path.mkdir(parents=True, exist_ok=True)
            return DirectoryOperationResponse(success=True, message=f"Directory created: {directory_path}")
        else:
            return DirectoryOperationResponse(success=False, message=f"Invalid directory operation: {operation}")
    except Exception as e:
        return DirectoryOperationResponse(success=False, message=f"Error performing directory operation: {str(e)}")

@fileops_proxy.register_for_execution()
@fileops_agent.register_for_llm(description="update_file")
def update_file(file_path: str, content: str) -> FileUpdateResponse:
    print(f"Current working directory: {os.getcwd()}")
    full_path = PLAYGROUND_DIRECTORY / Path(file_path)
    print(f"Full path: {full_path}")
    if not validate_path(full_path):
        return FileUpdateResponse(success=False, message=f"Access denied. File path is outside the playground: {file_path}")
    try:
        full_path.write_text(content)
        return FileUpdateResponse(success=True, message=f"File updated: {file_path}")
    except Exception as e:
        return FileUpdateResponse(success=False, message=f"Error updating file: {str(e)}")

@fileops_proxy.register_for_execution()
@fileops_agent.register_for_llm(description="list_directory")
def list_directory() -> ListDirectoryResponse:
    current_directory = os.getcwd()
    try:
        contents = [item.name for item in Path(current_directory).iterdir()]
        return ListDirectoryResponse(success=True, contents=contents, message=f"Directory contents listed: {current_directory}")
    except Exception as e:
        return ListDirectoryResponse(success=False, contents=[], message=f"Error listing directory contents: {str(e)}")

fileops_agent.llm_config["tools"]

assert fileops_proxy.function_map["read_file"]._origin == read_file
assert fileops_proxy.function_map["check_directory"]._origin == check_directory
assert fileops_proxy.function_map["change_directory"]._origin == change_directory
assert fileops_proxy.function_map["search_files"]._origin == search_files
assert fileops_proxy.function_map["perform_file_operation"]._origin == perform_file_operation
assert fileops_proxy.function_map["perform_directory_operation"]._origin == perform_directory_operation
assert fileops_proxy.function_map["update_file"]._origin == update_file
assert fileops_proxy.function_map["list_directory"]._origin == list_directory


############################################################################################################
# graph diagram
############################################################################################################

graph = nx.DiGraph()

# Add nodes
graph.add_nodes_from([agent.name for agent in file_agents])

# Add edges
for key, value in file_speaker_transitions_dict.items():
    for agent in value:
        if agent is not None:  # Check if agent is not None before accessing .name
            graph.add_edge(key.name, agent.name)
        else:
            print(f"Skipping None agent for key: {key.name}")
# Visualize

positions = {
    'file_response_agent':      (9, 4),
    'fileops_agent':            (8, 4),
    'fileops_proxy':            (6, 4),
    'fileops_userproxy':        (10, 4)
}

# Draw the graph with secret values annotated
plt.figure(figsize=(20, 15))
pos = nx.spring_layout(graph)  # positions for all nodes

# Draw nodes with their colors
nx.draw(graph, pos=positions, with_labels=True, font_weight="bold", node_size=3000, node_color='lightblue', font_size=7, arrows=True)

plt.show()

# File operations groupchat and manager
file_groupchat = GroupChat(
    agents=file_agents,
    messages=[],
    max_round=40,
    allowed_or_disallowed_speaker_transitions=file_speaker_transitions_dict,
    speaker_transitions_type="allowed",
)

file_manager = autogen.GroupChatManager(
    groupchat=file_groupchat, llm_config=manager_config, code_execution_config=False, is_termination_msg=is_termination_msg
)

#file_request= "Access the playground directory to read part 17 of 'Snow Crash' from the specified path"
#file_userproxy.initiate_chat(    file_manager,    message=("Access the playground directory to read notable conversations located in playground / books dir"+" current time: "+current_time + " " + json_format),)
def process_file_ops(file_request):
    # Save the current working directory
    original_directory = os.getcwd()

    try:
        # Change the directory to "agent_workspace"
        os.chdir("agent_workspace")

        # Convert the file request to JSON string
        user_request = json.dumps(file_request)

        # Initiate the chat and get the response
        chat_result = file_userproxy.initiate_chat(
            file_manager,
            message=(user_request + " current time: " + current_time + " " + json_format),
        )

        # Return the ChatResult object as the response
        return chat_result

    finally:
        # Change back to the original directory
        os.chdir(original_directory)