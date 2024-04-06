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
import Reading_list
from selenium.webdriver.chrome.service import Service
import memories.SelfSchema
import memories.system_messages_JSON as system_messages
from autogen.agentchat.groupchat import GroupChat
from autogen.agentchat.agent import Agent
from autogen.agentchat.assistant_agent import AssistantAgent
from autogen.agentchat import UserProxyAgent
from autogen.agentchat.conversable_agent import ConversableAgent
from autogen.agentchat.contrib.retrieve_assistant_agent import RetrieveAssistantAgent
from autogen.agentchat.contrib.capabilities.teachability import Teachability
from autogen.agentchat.contrib.web_surfer import WebSurferAgent  # noqa: E402
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
from interpreter import interpreter
from openinterpreter_agent import OpenInterpreterAgent

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException
import time

#logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
#logging_session_id = autogen.runtime_logging.start(config={"AGlogdb": "logs.db"})
#print("Logging session ID: " + str(logging_session_id))

os.environ['MULTION_API_KEY'] = "cc5e3f73ff5f47b7b0b2dac955c5dbd1"
os.environ["BING_API_KEY"] = "f894a0592bce49dabb03211fb6c3e3d2"

bing_api_key = os.environ["BING_API_KEY"]

class MultionAPI:
    def __init__(self, default_url="https://www.google.com"):
        self.default_url = default_url

    def browse(self, query: str, url: str = None, max_steps: int = 6) -> dict:
        if url is None:
            url = self.default_url
        response = multion.browse(
            {
                "cmd": query,
                "url": url,
                "maxSteps": max_steps
            }
        )
        return response

multion_api = MultionAPI()




# Replace 'your_extension_id' with the actual ID of the Multi-on Chrome extension
extension_id = 'ddmjhdbknfidiopmbaceghhhbgbpenmm'
#enable_extension(extension_id)


json_format = " Response must be in JSON format."

now = datetime.now()

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

summarizer_llm_config = {
    "timeout": 600,
    "cache_seed": 44,  # change the seed for different trials
    "config_list": autogen.config_list_from_json(
        "OAI_CONFIG_LIST",
        filter_dict={"model": ["gpt-3.5-turbo-1106", "gpt-3.5-turbo-16k-0613", "gpt-3.5-turbo-16k"]},
    ),
    "temperature": 0,
}

llm_config = {"config_list": config_list_text, 
              "seed": 42
              }


# Create an empty directed graph
web_agents = []
web_speaker_transitions_dict = {}


def get_agent_of_name(web_agents, name) -> Agent:
    for agent in web_agents:
        if agent.name == name:
            return agent


############################################################################################################
# Web SoM
############################################################################################################

web_agents.append(
    AssistantAgent(
        name="multion_agent",
        system_message=system_messages.multionagent_systemmessage,
        llm_config=llm_config,
        human_input_mode="NEVER",
        description="Call this Agent if a function call to use the internet is required."
    )
)

web_speaker_transitions_dict[web_agents[-1]] = []

multion_agent = web_agents[0]

web_agents.append(
    UserProxyAgent(
        name="multion_proxy",
        system_message=system_messages.multionproxy_systemmessage,
        llm_config=llm_config,
        description=""" DO NOT CALL THIS AGENT. Is is used for programatic function calling. Calling this agent results in infinite loops that achieve nothing.""",
        code_execution_config={"work_dir": "coding", "use_docker": False},
        human_input_mode="NEVER"
    )
)

web_speaker_transitions_dict[web_agents[-1]] = []

multion_proxy = web_agents[1]

web_agents.append(
    AssistantAgent(
        name="multion_response_agent",
        system_message=system_messages.multionagentresponse_systemmessage,
        llm_config=llm_config,
        human_input_mode="NEVER",
        description="""Call this Agent if: 

        The Multion_agent should call this agent:
            IF all requested function calls have returned a result, then call this agent.
            IF the request_state is `Complete`

        DO NOT CALL THIS AGENT IF:
            The Multion_agent is anwsering a complex query that takes multiple function calls, the multion_agent must be allowed to complete all the function calls, including a sensible number of retry attempts. 
            Do not engage this agent until the function calling process is complete.
        """
    )
)

web_speaker_transitions_dict[web_agents[-1]] = []

multion_response_agent = web_agents[2]


web_agents.append(
    WebSurferAgent(
        name="surf_agent",
        system_message="""You are a helpful web surfing agent""", #system_messages.multionagent_systemmessage,
        summarizer_llm_config=summarizer_llm_config,
        browser_config={"viewport_size": 4096, "bing_api_key": bing_api_key},
        llm_config=llm_config,
        human_input_mode="NEVER",
        description="Call this Agent if you need to access the internet."
    )
)

web_speaker_transitions_dict[web_agents[-1]] = []

surf_agent = web_agents[3]



web_agents.append(
    OpenInterpreterAgent(
        name="OpenI_agent",
        system_message="""You are a helpful web surfing agent""", #system_messages.multionagent_systemmessage,
        #summarizer_llm_config=summarizer_llm_config,
        #browser_config={"viewport_size": 4096, "bing_api_key": bing_api_key},
        llm_config=llm_config,
        api_key="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",
        human_input_mode="NEVER",
        description="Call this Agent if you need to access the internet."
    )
)

web_speaker_transitions_dict[web_agents[-1]] = []

OpenI_agent = web_agents[4]

try:
    from termcolor import colored
except ImportError:

    def colored(x, *args, **kwargs):
        return x

def is_termination_msg(content) -> bool:
    have_content = content.get("content", None) is not None
    if have_content and "TERMINUS" in content["content"]:
        return True
    return False


# Terminates the conversation when TERMINATE is detected.

web_agents.append(
    UserProxyAgent(
        name="web_userproxy",
        system_message="Terminator admin. Reply in JSON",
        code_execution_config=False,
        is_termination_msg=is_termination_msg,
        human_input_mode="NEVER",
    )
)
web_speaker_transitions_dict[web_agents[-1]] = []

web_userproxy= web_agents[5]

############################################################################################################
# Speaker Transitions
############################################################################################################

#Inbound 
web_speaker_transitions_dict[get_agent_of_name(web_agents, "web_userproxy")].append(get_agent_of_name(web_agents, name="multion_response_agent"))

# Web Xfer
web_speaker_transitions_dict[get_agent_of_name(web_agents, "multion_response_agent")].append(get_agent_of_name(web_agents, name="multion_agent"))
#web_speaker_transitions_dict[get_agent_of_name(web_agents, "multion_response_agent")].append(get_agent_of_name(web_agents, name="OpenI_agent"))
#web_speaker_transitions_dict[get_agent_of_name(web_agents, "OpenI_agent")].append(get_agent_of_name(web_agents, name="multion_response_agent"))
web_speaker_transitions_dict[get_agent_of_name(web_agents, "multion_response_agent")].append(get_agent_of_name(web_agents, name="surf_agent"))
web_speaker_transitions_dict[get_agent_of_name(web_agents, "surf_agent")].append(get_agent_of_name(web_agents, name="multion_response_agent"))
web_speaker_transitions_dict[get_agent_of_name(web_agents, "multion_agent")].append(get_agent_of_name(web_agents, name="multion_proxy"))
web_speaker_transitions_dict[get_agent_of_name(web_agents, "multion_proxy")].append(get_agent_of_name(web_agents, name="multion_agent"))
web_speaker_transitions_dict[get_agent_of_name(web_agents, "multion_agent")].append(get_agent_of_name(web_agents, name="multion_response_agent"))

#Exec Function Response Transfers
web_speaker_transitions_dict[get_agent_of_name(web_agents, "multion_response_agent")].append(get_agent_of_name(web_agents, name="web_userproxy"))


#visualize_speaker_transitions_dict(allowed_speaker_transitions_dict, agents)
# Visualization only







############################################################################################################
# graph diagram
############################################################################################################

graph = nx.DiGraph()

# Add nodes
graph.add_nodes_from([agent.name for agent in web_agents])

# Add edges
for key, value in web_speaker_transitions_dict.items():
    for agent in value:
        if agent is not None:  # Check if agent is not None before accessing .name
            graph.add_edge(key.name, agent.name)
        else:
            print(f"Skipping None agent for key: {key.name}")
# Visualize

positions = {
    'multion_agent':            (8, 4),
    'multion_proxy':            (6, 4),
    'multion_response_agent':   (10, 6),
    'surf_agent':               (9, 6),
    'OpenI_agent':               (11, 6),
    'web_userproxy':            (10, 4)
}

# Draw the graph with secret values annotated
plt.figure(figsize=(20, 15))
pos = nx.spring_layout(graph)  # positions for all nodes

# Draw nodes with their colors
nx.draw(graph, pos=positions, with_labels=True, font_weight="bold", node_size=3000, node_color='lightblue', font_size=7, arrows=True)

plt.show()


# Termination message detection

############################################################################################################
# Web Functions
############################################################################################################



@multion_proxy.register_for_execution()
@multion_agent.register_for_llm(description="Perform a Multi-on search")
def perform_multion_search(query: str, url: str = None, max_steps: int = 6) -> dict:
    return multion_api.browse(query, url, max_steps)


############################################################################################################
# Manager, group and run
############################################################################################################


web_group_chat = GroupChat(
    agents=web_agents,
    messages=[],
    max_round=40,
    allowed_or_disallowed_speaker_transitions=web_speaker_transitions_dict,
    speaker_transitions_type="allowed",
)


# Create the manager
web_manager = autogen.GroupChatManager(
    groupchat=web_group_chat, llm_config=manager_config, code_execution_config=False, is_termination_msg=is_termination_msg
)

#web_userproxy.initiate_chat(    web_manager,    message=("How many studio albums were published by Mercedes Sosa between 2000 and 2009 (included)? You can use the latest 2022 version of english wikipedia."+" current time: "+current_time + " " + json_format),)
def process_web(web_request):
    # Convert the goal context to JSON string
    user_request = json.dumps(web_request)

    # Initiate the chat and get the response
    chat_result = web_userproxy.initiate_chat(
        web_manager,
        message=(user_request + " current time: " + current_time + " " + json_format + "web group"),
    )

    # Return the ChatResult object as the response
    return chat_result