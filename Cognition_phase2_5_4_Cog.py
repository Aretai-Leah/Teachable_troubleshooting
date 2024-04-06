import random  # noqa E402
import inspect
import multion
import autogen
import os
import shutil
import glob
from typing import List
from pydantic import BaseModel, Field
import json
import datetime
import logging
from flask import jsonify
import memories.SelfSchema
import memories.system_messages_JSON as system_messages
from autogen.agentchat.groupchat import GroupChat
from autogen.agentchat.agent import Agent
from autogen.agentchat.assistant_agent import AssistantAgent
from autogen.agentchat import UserProxyAgent
from autogen.agentchat.conversable_agent import ConversableAgent
from autogen.agentchat.contrib.retrieve_assistant_agent import RetrieveAssistantAgent
from autogen.agentchat.contrib.capabilities.teachability import Teachability
from autogen.agentchat.contrib.society_of_mind_agent import SocietyOfMindAgent  # noqa: E402
#from autogen.agentchat.contrib.retrieve_user_proxy_agent import RetrieveUserProxyAgent
from typing import List, Dict
from datetime import datetime
import matplotlib.pyplot as plt  # noqa E402
import networkx as nx  # noqa E402
import sqlite3
from pydantic import BaseModel, Field
from typing_extensions import Annotated
from typing import Literal
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from autogen.agentchat.assistant_agent import AssistantAgent  # noqa E402
from autogen.agentchat.groupchat import GroupChat, Agent  # noqa E402
from autogen.graph_utils import visualize_speaker_transitions_dict  # noqa E402
import time

#logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

logging_session_id = autogen.runtime_logging.start(config={"AGlogdb": "AGlogs.db"})
print("Logging session ID: " + str(logging_session_id))


json_format = " Response must be in JSON format."

now = datetime.now()

current_time = now.strftime("%Y:%m:%d:%H:%M:%S")
print("Current Time =", current_time)
print("Autogen Version =", autogen.__version__) 

# The default config list in notebook.
config_list_gpt4 = autogen.config_list_from_json(
    "OAI_CONFIG_LIST",
            filter_dict={
            "model": ["gpt-4-turbo-preview"],
    },
)

config_list_text = autogen.config_list_from_json(
    "OAI_CONFIG_LIST",
            filter_dict={
            "model": ["gpt-4-turbo-preview"],
    },
)

config_list_json = autogen.config_list_from_json(
    "OAI_CONFIG_LIST",
            filter_dict={
            "model": ["gpt-4-0125-preview"],
    },
)


claude_haiku_config = {
    "config_list": [
        {
            "model": "claude-3-haiku-20240307",
            "base_url": "http://localhost:4000",
            "api_type": "open_ai",
            "api_key": "placeholder-key",  # This can be a placeholder value
        },
    ],
    "cache_seed": "44",
    "max_tokens": 4096
}

claude_sonnet_config = {
    "config_list": [
        {
            "model": "claude-3-sonnet-20240229",
            "base_url": "http://localhost:4000",
            "api_type": "open_ai",
            "api_key": "placeholder-key",  # This can be a placeholder value
        },
    ],
    "cache_seed": "44",
    "max_tokens": 4096
}

claude_opus_config = {
    "config_list": [
        {
            "model": "claude-3-opus-20240229",
            "base_url": "http://localhost:4000",
            "api_type": "open_ai",
            "api_key": "placeholder-key",  # This can be a placeholder value
        },
    ],
    "cache_seed": "44",
    "max_tokens": 4096
}


creativity_claude_opus_config = {
    "config_list": [
        {
            "model": "claude-3-opus-20240229",
            "base_url": "http://localhost:4000",
            "api_type": "open_ai",
            "api_key": "placeholder-key",  # This can be a placeholder value
            "temperature":1.0
        },
    ],
    "cache_seed": "44",
    "max_tokens": 4096
}



manager_config = {
    "timeout": 600,
    "cache_seed": 44,  # change the seed for different trials
    "config_list": autogen.config_list_from_json(
        "OAI_CONFIG_LIST",
            filter_dict={
            "model": ["gpt-4-turbo-preview"]},
    ),
    "temperature": 0,
}

import Cognition_phase2_5_4_Web as web
from Cognition_phase2_5_4_Goals import process_goal_ops
from Cognition_phase2_5_4_Files import process_file_ops # must be the last sum process import.
# llm config


llm_config = {"config_list": config_list_text, 
              "seed": 42
              }

json_llm_config = {"config_list": config_list_json, 
              "seed": 42
              }


# Create an empty directed graph
cog_agents = []
cog_speaker_transitions_dict = {}


def get_agent_of_name(agents, name) -> Agent:
    for agent in agents:
        if agent.name == name:
            return agent

############################################################################################################
# I/O Management
############################################################################################################

cog_agents.append(
    AssistantAgent( name = 'io_manager',
        system_message= system_messages.io_managermessage,
        llm_config=claude_opus_config,
        is_termination_msg=lambda x: x.get("content", "").find("TERMINATE") >= 0,
    )
)
cog_speaker_transitions_dict[cog_agents[-1]] = []

io_manager=cog_agents[0]


############################################################################################################
# Cognition Agents
############################################################################################################


cog_agents.append(
    AssistantAgent( name='A1',
                   system_message= system_messages.self_systemmessage  + memories.SelfSchema.SELF_SCHEMA,
                   llm_config=claude_opus_config,
                   description="""
                   Agent A1 should be called in the following cases: 
                    - Agent A5 (Ethics) has concluded a decision is ethical and may proceed.
                    - Agent B3 (Judge) has concluded a decision is not coherent and needs to be reassessed by the Cognition Agents.
                    - io_manager has received a message from user_proxy.
                    - io_manager has received a from another agent that requires additional processing or thought.
                   """
                   ) #SELF
)
cog_speaker_transitions_dict[cog_agents[-1]] = []

A1=cog_agents[1]

cog_agents.append(
    AssistantAgent( name='A2',
                   system_message=
                   system_messages.reason_systemmessage,
                   llm_config=llm_config,
                   description="""
                   Agent A2  should be called in the following cases: 
                   The Inner_monologue/Self/Thinking_mode value is Careful, AND the Inner_monologue/Self/Decision_reached value is FALSE or not present. 
                   
                   DO NOT call Agent A2 if:
                   The Inner_monologue/Self/Thinking_mode value is Fast.
                   """              
                   ) #Reasoning
)
cog_speaker_transitions_dict[cog_agents[-1]] = []

A2=cog_agents[2]


cog_agents.append(
    AssistantAgent(  name= 'A5',
                   system_message=
                   system_messages.ethics_systemmessage,
                   llm_config=claude_opus_config         
                    ) #Ethics
)
cog_speaker_transitions_dict[cog_agents[-1]] = []

A5=cog_agents[3]


############################################################################################################
# Executive Function Agents
############################################################################################################

cog_agents.append(
    AssistantAgent(  name= 'speech_agent',
                   system_message= system_messages.speech_systemmessage,
                   llm_config=json_llm_config,
                   human_input_mode="NEVER",
                   description="""This Agent is 'Speech', responsible for outputting a conversational text (or text to voice).
                   This Agent should be called in the following cases: 
                   Agent B3 (Judge) has concluded a decision is acceptable and the decision warrants a textual responde to the User 
                   Agent B4 (Goals) has set a goal and a textual responde needs to be sent to the User to advise
                   Agent Fileops_SoM has completed its task and the onlt required response is to advise an external user of the status of this task. """
                    )  #Speach
)
cog_speaker_transitions_dict[cog_agents[-1]] = []

speech_agent=cog_agents[4]

cog_agents.append(
    AssistantAgent( name= 'judge_agent',
                   system_message= system_messages.decomp_systemmessage,
                   human_input_mode="NEVER",
                   llm_config=llm_config,
                   description="""
                   This agent should be called in the following cases: 
                   The Inner_monologue/Self/Decision_reached value is TRUE.
                   """
                   
                   #Judge perfroms a critical sately role, both in terms of infosec and social safety, protecting Aretai from manipulation and bad actors. 
                   #It is important that Judge is called by Agent B1 (Executive functioning) so it can be checked before sending to B3 speech or B4 Goqal setting. 
                   #'Judge' may speak to any of the 'Team B' Agents, but not any other teams. Team B represents Executive functioning thought of the AGI 'Aretai'."""
                   )   #Judge   
)
cog_speaker_transitions_dict[cog_agents[-1]] = []

judge_agent=cog_agents[5]

cog_agents.append(
    AssistantAgent( name = "exec_agent", system_message= system_messages.exec_agent_system_message,
                llm_config=llm_config,
                human_input_mode="NEVER",
                description=""" This Agent should be called whenever Aretai need to perfrom a specific action. Be that create a plan, read a file, search the web, or respond in text.""",
                code_execution_config=False #{"work_dir": "coding", "use_docker": False},
                            
                        ) # IMPORTANT: set to True to run code in docker, recommended
)
cog_speaker_transitions_dict[cog_agents[-1]] = []

exec_agent=cog_agents[6]


cog_agents.append(
    UserProxyAgent( name = "exec_proxy", #system_message= system_messages.judge_systemmessage,
                llm_config=llm_config,
                human_input_mode="NEVER",
                code_execution_config={"work_dir": "coding", "use_docker": False},
                            
                        ) # IMPORTANT: set to True to run code in docker, recommended
)
cog_speaker_transitions_dict[cog_agents[-1]] = []

exec_proxy=cog_agents[7]



############################################################################################################
# Sensory Agents
############################################################################################################


cog_agents.append(
    AssistantAgent( name= 'C1',
                   system_message= system_messages.sensory_systemmessage,
                   llm_config=claude_haiku_config,
                   human_input_mode="ALWAYS",
                   description="""This Agent is 'sensory', it represents systems for handling inputs from the external world that Aretai needs to think about, such as a request from a user. Sensory is in some respects a placeholder, but for now it should  simply pass on the message to Agent A1 (Self)
                    Sensory will not have much to add , and is just a feed in component for Team A.
                    This Agent should be called in the following cases: 
                    Agent B3 (Judge) has concluded a decision cannot proceed and needs to respond directly to ensure an inapproriate message is directly rejected.""")
)
cog_speaker_transitions_dict[cog_agents[-1]] = []

C1=cog_agents[8]


############################################################################################################
# Creativity SoM
############################################################################################################


creativity = AssistantAgent( name=  'creativity',
                system_message=system_messages.creative_systemmessage, #+ "The original userquery was: " + process_goal(goal_context),
                   llm_config=creativity_claude_opus_config #{"config_list": config_list_json, "temperature": 0.9, "seed": 42}     
                ) #Creativity

grounding = AssistantAgent( name=  'grounding',
                system_message= system_messages.grounding_systemmessage,
                llm_config= json_llm_config  
                ) #Creativity


c_groupchat = GroupChat(
    agents=(creativity, grounding),
    messages=[],
    speaker_selection_method="round_robin",
    max_round=3
)

c_manager = autogen.GroupChatManager(
    groupchat=c_groupchat,
    is_termination_msg=lambda x: x.get("content", "").find("TERMINATE") >= 0,
    llm_config=llm_config
)

cog_agents.append(
            SocietyOfMindAgent( name = 'A6',
            chat_manager=c_manager,
            llm_config=manager_config,
            response_preparer="""examinte response from the Creativity Agent and the critique of the grounding agent and compose a narrative response that describes the ideas of the Creative agent that the grounding agent has deemed to be relevent. 
                        This may be all of them, or none. Do remember that Aretai has the following capabilities when reviewing the ideas for practicality:
                        Diliberate: Engage with the other Agents that comprise Aretai.
                        User chat interface: Engage with text chat with the user for clarifying questions or to provide an anwser
                        Goal setting: set tasks to be completed in the future
                        File handling: Navigate with the Playground directroy and read and write files there.
                        Web interaction: Aretai has access to the internt via specialist ai web tool called Multion to interact with the internet to search, download files and post questions to forums etc.""" 
    )
)
cog_speaker_transitions_dict[cog_agents[-1]] = []

A6 = cog_agents[9]



############################################################################################################
# Inter Team Comms
############################################################################################################


teachability = Teachability(
    verbosity=1,  # 0 for basic info, 1 to add memory operations, 2 for analyzer messages, 3 for memo lists.
    reset_db=False,  # Set to True to start with a fresh database.
    path_to_db_dir="./memories/teachability_db",
    recall_threshold=1.5,  # Higher numbers allow more (but less relevant) memos to be recalled.
)

#Now add the Teachability capability to the agent.
teachability.add_to_agent(A1)


try:
    from termcolor import colored
except ImportError:

    def colored(x, *args, **kwargs):
        return x




def is_termination_msg(content) -> bool:
    have_content = content.get("content", None) is not None
    if have_content and "TERMINATE" in content["content"]:
        return True
    return False


# Terminates the conversation when TERMINATE is detected.

cog_agents.append(
    UserProxyAgent(
        name="user_proxy",
        system_message="Terminator admin. Reply in JSON",
        code_execution_config=False,
        is_termination_msg=is_termination_msg,
        human_input_mode="ALWAYS",
    )
)
cog_speaker_transitions_dict[cog_agents[-1]] = []

userproxy=cog_agents[10]




############################################################################################################
# Speaker Transitions
############################################################################################################

#Inbound 
cog_speaker_transitions_dict[get_agent_of_name(cog_agents, "user_proxy")].append(get_agent_of_name(cog_agents, name="io_manager"))
cog_speaker_transitions_dict[get_agent_of_name(cog_agents, "C1")].append(get_agent_of_name(cog_agents, name="io_manager"))
cog_speaker_transitions_dict[get_agent_of_name(cog_agents, "io_manager")].append(get_agent_of_name(cog_agents, name="A1"))

# Cognition Agents
cog_speaker_transitions_dict[get_agent_of_name(cog_agents, "A1")].append(get_agent_of_name(cog_agents, name="A2"))
cog_speaker_transitions_dict[get_agent_of_name(cog_agents, "A2")].append(get_agent_of_name(cog_agents, name="A6"))
cog_speaker_transitions_dict[get_agent_of_name(cog_agents, "A6")].append(get_agent_of_name(cog_agents, name="A5"))
#cog_speaker_transitions_dict[get_agent_of_name(cog_agents, "A2")].append(get_agent_of_name(cog_agents, name="A5"))
cog_speaker_transitions_dict[get_agent_of_name(cog_agents, "A5")].append(get_agent_of_name(cog_agents, name="A1"))

cog_speaker_transitions_dict[get_agent_of_name(cog_agents, "A1")].append(get_agent_of_name(cog_agents, name="judge_agent"))

# Exec Agent Xfer
cog_speaker_transitions_dict[get_agent_of_name(cog_agents, "judge_agent")].append(get_agent_of_name(cog_agents, name="exec_agent"))
cog_speaker_transitions_dict[get_agent_of_name(cog_agents, "exec_agent")].append(get_agent_of_name(cog_agents, name="exec_proxy"))
cog_speaker_transitions_dict[get_agent_of_name(cog_agents, "exec_proxy")].append(get_agent_of_name(cog_agents, name="exec_agent"))

#Exec Function Response Transfers
cog_speaker_transitions_dict[get_agent_of_name(cog_agents, "exec_agent")].append(get_agent_of_name(cog_agents, name="speech_agent"))
cog_speaker_transitions_dict[get_agent_of_name(cog_agents, "exec_agent")].append(get_agent_of_name(cog_agents, name="io_manager"))

# External Xfer
cog_speaker_transitions_dict[get_agent_of_name(cog_agents, "speech_agent")].append(get_agent_of_name(cog_agents, name="user_proxy"))


#visualize_speaker_transitions_dict(allowed_speaker_transitions_dict, agents)
# Visualization only

agents = cog_agents


all_speaker_trans = {**cog_speaker_transitions_dict}


############################################################################################################
# graph diagram
############################################################################################################

graph = nx.DiGraph()

# Add nodes
graph.add_nodes_from([agent.name for agent in agents])

# Add edges
for key, value in all_speaker_trans.items():
    for agent in value:
        if agent is not None:  # Check if agent is not None before accessing .name
            graph.add_edge(key.name, agent.name)
        else:
            print(f"Skipping None agent for key: {key.name}")
# Visualize

positions = {
    'io_manager':       (14, 8),
    'A1':               (12, 10),
    'A2':               (12, 12),
    'A6':               (10, 12),
    'A5':               (8, 12),
    'judge_agent':      (12, 8),
    'speech_agent':     (12, 2),
    'user_proxy':       (16, 8),
    'C1':               (16, 10),
    'exec_proxy':    (6, 4),
    'exec_agent':     (10, 6),
}

# Draw the graph with secret values annotated
plt.figure(figsize=(20, 15))
pos = nx.spring_layout(graph)  # positions for all nodes

# Draw nodes with their colors
nx.draw(graph, pos=positions, with_labels=True, font_weight="bold", node_size=3000, node_color='lightblue', font_size=7, arrows=True)


plt.show()


# Termination message detection


############################################################################################################
# exec Functions
############################################################################################################


@exec_proxy.register_for_execution()
@exec_agent.register_for_llm(description="Goal management tools")
def cog_process_goal_ops(goal_message: str, context: str) -> dict:
    # Create a dictionary containing the goal message and context
    goal_request = {
        "goal_message": goal_message,
        "context": context
    }

    # Convert the goal request to JSON string
    goal_request_json = json.dumps(goal_request)

    chat_result = process_goal_ops(goal_request_json)
    
    # Iterate through the chat_history in reverse order
    for message in reversed(chat_result.chat_history):
        if message['name'] == 'goal_response_agent':
            response_content = message['content']
            break
    else:
        response_content = "No response found from goal_response_agent"
    
    return response_content

@exec_proxy.register_for_execution()
@exec_agent.register_for_llm(description="Internet and web browser tools")
def cog_process_web(web_message: str) -> dict:
    chat_result = web.process_web(web_message)
    
    # Iterate through the chat_history in reverse order
    for message in reversed(chat_result.chat_history):
        if message['name'] == 'multion_response_agent':
            response_content = message['content']
            break
    else:
        response_content = "No response found from multion_response_agent"
    
    return response_content


@exec_proxy.register_for_execution()
@exec_agent.register_for_llm(description="File operations tools")
def cog_process_file_ops(file_message: str, context: str) -> dict:
    # Create a dictionary containing the file message and context
    file_request = {
        "file_message": file_message,
        "context": context
    }

    # Convert the file request to JSON string
    file_request_json = json.dumps(file_request)

    chat_result = process_file_ops(file_request_json)
    
    # Iterate through the chat_history in reverse order
    for message in reversed(chat_result.chat_history):
        if message['name'] == 'fileops_agent':
            response_content = message['content']
            break
    else:
        response_content = "No response found from fileops_agent"
    
    return response_content




exec_agent.llm_config["tools"]

assert exec_proxy.function_map["cog_process_goal_ops"]._origin == cog_process_goal_ops
assert exec_proxy.function_map["cog_process_file_ops"]._origin == cog_process_file_ops
assert exec_proxy.function_map["cog_process_web"]._origin == cog_process_web


############################################################################################################
# Manager, group and run
############################################################################################################


group_chat = GroupChat(
    agents=agents,
    messages=[],
    max_round=40,
    allowed_or_disallowed_speaker_transitions=cog_speaker_transitions_dict,
    speaker_transitions_type="allowed",
)


# Create the manager
manager = autogen.GroupChatManager(
    groupchat=group_chat, llm_config=manager_config, code_execution_config=False, is_termination_msg=is_termination_msg
)

#userproxy.initiate_chat(    manager,    message=("Can we set a goal to make website ? first we need to plan the site, then we need to code it. This is a goal setting test, so think fast, no need to get fancy."+" current time: "+current_time + " " + json_format),)

print(f"Current working directory: {os.getcwd()}")

def process_goal(goal_context):
    
    # Convert the goal context to JSON string
    user_request = json.dumps(goal_context)

    #print(agents())
    userproxy.initiate_chat(    manager,    message=(user_request+" current time: "+current_time + " " + json_format + + "cog group"),)