"""Pure reusable three-stage animation clocks, embedded in registered renderers."""


def action_smooth(value):
    value=max(0.,min(1.,value));return value*value*(3.-2.*value)


def action_clock(q):
    """Establish first, perform the action, then hold the legible result."""
    return action_smooth((q-.20)/.58)


def action_phase(q):
    return 'setup' if q<.20 else 'action' if q<.78 else 'result'
