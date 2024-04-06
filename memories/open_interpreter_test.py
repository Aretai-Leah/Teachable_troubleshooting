from interpreter import interpreter
from interpreter import computer
#from interpreter import computer

interpreter.auto_run = True


from interpreter import interpreter
from interpreter.terminal_interface.terminal_interface import terminal_interface
interpreter.llm.api_key = "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"

result = terminal_interface(interpreter, "what is the temperature in vladivostok today?")

# Print the response
for chunk in result:
    print(chunk)