"""Execution tracing for the agent graph (timestamped spans + graph builder).

Neutral package: pipeline modules may import it; it imports nothing from
lock/outbound, so the human-lock boundary tests still hold.
"""
