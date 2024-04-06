import os
import json
from datetime import datetime
import sqlite3
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

# llm config
llm_config = {"config_list": config_list_json, 
              "seed": 42
              }

# Goal function agents
goal_agents = []
goal_speaker_transitions_dict = {}

def get_agent_of_name(goal_agents, name) -> Agent:
    for agent in goal_agents:
        if agent.name == name:
            return agent

goal_agents.append(
    AssistantAgent(
        name="goal_agent",
        system_message=system_messages.goals_systemmessage,
        llm_config=llm_config,
        human_input_mode="NEVER",
        description="""
        This Agent should be called by goal_response_agent when there is a new incoming task.
        """,
        code_execution_config=False,
    )
)
goal_speaker_transitions_dict[goal_agents[-1]] = []

goal_agent = goal_agents[0]

goal_agents.append(
    UserProxyAgent(
        name="goal_proxy",
        llm_config=llm_config,
        description=""" DO NOT CALL THIS AGENT. It is used for programmatic function calling. Calling this agent results in infinite loops that achieve nothing.""",
        code_execution_config=False,
        human_input_mode="NEVER",
    )
)
goal_speaker_transitions_dict[goal_agents[-1]] = []

goal_proxy = goal_agents[1]

goal_agents.append(
    AssistantAgent(
        name="goal_response_agent",
        system_message=system_messages.goalagentresponse_systemmessage,
        llm_config=llm_config,
        human_input_mode="NEVER",
        description="""Call this Agent if:

        The goal_agent should call this agent:
            IF all requested function calls have returned a result, then call this agent.
            IF the request_state is `goal_created`

        DO NOT CALL THIS AGENT IF:
            The goal_agent is answering a complex query that takes multiple function calls, the goal_agent must be allowed to complete all the function calls, including a sensible number of retry attempts.
            Do not engage this agent until the function calling process is complete.
        """
    )
)

goal_speaker_transitions_dict[goal_agents[-1]] = []

goal_response_agent = goal_agents[2]

def is_termination_msg(content) -> bool:
    have_content = content.get("content", None) is not None
    if have_content and "TERMINUS" in content["content"]:
        return True
    return False

goal_agents.append(
    UserProxyAgent(
        name="goal_userproxy",
        system_message="Terminator admin. Reply in JSON",
        code_execution_config=False,
        description=""" DO NOT CALL THIS AGENT. It is used for programmatic function calling. Calling this agent results in infinite loops that achieve nothing.""",
        is_termination_msg=is_termination_msg,
        human_input_mode="NEVER",
    )
)
goal_speaker_transitions_dict[goal_agents[-1]] = []

goal_userproxy = goal_agents[3]

# Speaker transitions
goal_speaker_transitions_dict[get_agent_of_name(goal_agents, "goal_userproxy")].append(get_agent_of_name(goal_agents, name="goal_response_agent"))
goal_speaker_transitions_dict[get_agent_of_name(goal_agents, "goal_response_agent")].append(get_agent_of_name(goal_agents, name="goal_agent"))
goal_speaker_transitions_dict[get_agent_of_name(goal_agents, "goal_agent")].append(get_agent_of_name(goal_agents, name="goal_proxy"))
goal_speaker_transitions_dict[get_agent_of_name(goal_agents, "goal_proxy")].append(get_agent_of_name(goal_agents, name="goal_agent"))
goal_speaker_transitions_dict[get_agent_of_name(goal_agents, "goal_agent")].append(get_agent_of_name(goal_agents, name="goal_response_agent"))
goal_speaker_transitions_dict[get_agent_of_name(goal_agents, "goal_response_agent")].append(get_agent_of_name(goal_agents, name="goal_userproxy"))



############################################################################################################
# Goal Functions
############################################################################################################



# Goal functions
@goal_proxy.register_for_execution()
@goal_agent.register_for_llm(description="goal creator")
def create_goal(goal_name: str, goal_description: str, trigger_time: str) -> int:
    conn = sqlite3.connect('D:\Github\Aretai-AGI\logs.db')
    try:
        c = conn.cursor()
        c.execute("INSERT INTO goals (goal_name, goal_description, trigger_time, status) VALUES (?, ?, ?, ?)", (goal_name, goal_description, trigger_time, "unactioned"))
        conn.commit()
        return "goal created, ID: " + str(c.lastrowid)
    except sqlite3.Error as e:
        print(f"Error creating goal: {e}")
        return f"Error creating goal: {e}"
    finally:
        conn.close()

@goal_proxy.register_for_execution()
@goal_agent.register_for_llm(description="goal retriever")
def retrieve_goal(goal_id: int) -> dict:
    conn = sqlite3.connect('D:\Github\Aretai-AGI\logs.db')
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM goals WHERE id = ?", (goal_id,))
        goal = c.fetchone()
        if goal:
            return {
                "id": goal[0],
                "goal_name": goal[1],
                "goal_description": goal[2],
                "trigger_time": goal[3],
                "status": goal[4]
            }
        else:
            return "Goal not found"
    except sqlite3.Error as e:
        print(f"Error retrieving goal: {e}")
        return f"Error retrieving goal: {e}"
    finally:
        conn.close()

@goal_proxy.register_for_execution()
@goal_agent.register_for_llm(description="goal updater")
def update_goal(goal_id: int, update_data: dict) -> str:
    conn = sqlite3.connect('D:\Github\Aretai-AGI\logs.db')
    try:
        c = conn.cursor()
        for key, value in update_data.items():
            c.execute(f"UPDATE goals SET {key} = ? WHERE id = ?", (value, goal_id))
        conn.commit()
        return "Goal updated successfully"
    except sqlite3.Error as e:
        print(f"Error updating goal: {e}")
        return f"Error updating goal: {e}"
    finally:
        conn.close()

goal_agent.llm_config["tools"]

assert goal_proxy.function_map["create_goal"]._origin == create_goal
assert goal_proxy.function_map["retrieve_goal"]._origin == retrieve_goal
assert goal_proxy.function_map["update_goal"]._origin == update_goal



############################################################################################################
# graph diagram
############################################################################################################



graph = nx.DiGraph()

# Add nodes
graph.add_nodes_from([agent.name for agent in goal_agents])

# Add edges
for key, value in goal_speaker_transitions_dict.items():
    for agent in value:
        if agent is not None:  # Check if agent is not None before accessing .name
            graph.add_edge(key.name, agent.name)
        else:
            print(f"Skipping None agent for key: {key.name}")
# Visualize

positions = {
    'goal_response_agent':      (9, 4),
    'goal_agent':            (8, 4),
    'goal_proxy':            (6, 4),
    'goal_userproxy':        (10, 4)
}

# Draw the graph with secret values annotated
plt.figure(figsize=(20, 15))
pos = nx.spring_layout(graph)  # positions for all nodes

# Draw nodes with their colors
nx.draw(graph, pos=positions, with_labels=True, font_weight="bold", node_size=3000, node_color='lightblue', font_size=7, arrows=True)

plt.show()






# Goal groupchat and manager
goal_groupchat = GroupChat(
    agents=goal_agents,
    messages=[],
    max_round=40,
    allowed_or_disallowed_speaker_transitions=goal_speaker_transitions_dict,
    speaker_transitions_type="allowed",
)

goal_manager = autogen.GroupChatManager(
    groupchat=goal_groupchat, llm_config=manager_config, code_execution_config=False, is_termination_msg=is_termination_msg
)

#goal_request = "please create a goal to eat a pie for breakfast tomorrow."
#goal_userproxy.initiate_chat(    goal_manager,    message=("please create a goal to eat a pie for breakfast tomorrow."+" current time: "+current_time + " " + json_format),)
def process_goal_ops(goal_request):
    # Convert the goal request to JSON string
    user_request = json.dumps(goal_request)

    # Initiate the chat and get the response
    chat_result = goal_userproxy.initiate_chat(
        goal_manager,
        message=(user_request + " current time: " + current_time + " " + json_format),
    )

    # Return the ChatResult object as the response
    return chat_result