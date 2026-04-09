class StateResult:
    """Represents the result of a state transition in the chatbot FSM"""
    def __init__(self, reply, next_step=None):
        self.reply = reply
        self.next_step = next_step
