from flask import flash

def flasher(text, color=None):
    if color is None:
        color = ''
    else:
        color = 'is-' + color
    flash({'text': text, 'type': color})
