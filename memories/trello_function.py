import logging
from trello import TrelloClient
import trello_config as config

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


logging.debug(f"API Key: {config.API_KEY}, API Token: {config.API_TOKEN}")
logging.debug(f"API Key type: {type(config.API_KEY)}, API Token type: {type(config.API_TOKEN)}")



def create_trello_card(card_name, card_description, list_alias, due_date):
    client = TrelloClient(api_key=config.API_KEY, token=config.API_TOKEN)
    board = client.get_board(config.BOARD_ID)
    list_id = config.LIST_IDS.get(list_alias)
    
    if not list_id:
        raise ValueError(f"List alias '{list_alias}' is not defined in trello_config.py")
    
    trello_list = board.get_list(list_id)
    
    # Fetch label from the config
    labels = board.get_labels()
    selected_labels = [label for label in labels if label.name == config.LABEL_NAME]

    # Create the card
    new_card = trello_list.add_card(name=card_name, desc=card_description, labels=selected_labels, due=due_date)
    return new_card

# Example usage
card_name = 'twinetest2'
card_description = 'ropey'
list_alias = 'immediate_goals'
due_date = '2024-12-31'

try:
    card = create_trello_card(card_name, card_description, list_alias, due_date)
    print(f"Created card: {card.name}")
except Exception as e:
    logging.error(f"An error occurred: {e}", exc_info=True)










