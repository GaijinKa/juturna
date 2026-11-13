"""Pygments styles for the Juturna docs: the Meetecho code colours on navy."""

from pygments.style import Style
from pygments.token import Comment, Keyword, Name, Operator, String, Token


class MeetechoStyle(Style):
    """Code on the navy ground of the light theme."""

    background_color = '#0a1f2c'
    highlight_color = '#16405a'
    styles = {
        Token: '#e4edf3',
        Comment: 'italic #7fa3bd',
        Keyword: '#52a8ec',
        Operator.Word: '#52a8ec',
        Name.Builtin: '#52a8ec',
        String: '#a8e0b5',
    }


class MeetechoDarkStyle(MeetechoStyle):
    """Code on the darker navy ground of the dark theme."""

    background_color = '#06121a'
