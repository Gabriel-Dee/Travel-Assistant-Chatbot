from src.chatbot.interaction import handle_user_interaction
from unittest.mock import patch

def test_user_interaction_approval():
    with patch('builtins.input', return_value='y'):
        # Test user approving action
        pass  # Add test implementation

def test_user_interaction_denial():
    with patch('builtins.input', return_value='no, please change the flight time'):
        # Test user denying action
        pass  # Add test implementation