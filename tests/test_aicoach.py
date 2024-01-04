import pytest
from rich import print
from aicoach import AICoach


def test_function_smurf_detection():
    aicoach = AICoach()
    

    handle = "2-S2-1-691545"

    message = f"I am playing someone on around 3000 MMR. The player I am playing with has the handle toon handle '{handle}'. Can you tell me if they are a smurf?"

    response = aicoach.create_thread(message)
    
    assert isinstance(response, str)
    assert len(response) > 0
    print(response)


def test_function_query_build_order():
    aicoach = AICoach()

    message = f"My player ID is 'zatic'. Get the build order of the opponent of the last 5 games I played against 'protoss' opponents."

    response = aicoach.create_thread(message)

    assert isinstance(response, str)
    assert len(response) > 0
    print(response)


def test_init_from_scanner():
    aicoach = AICoach()
    
    map = "Acropolis LE"
    opponent = "Driftoss"
    mmr = "3786"
    message = aicoach.initiate_from_scanner(map, opponent, mmr)
    
    assert isinstance(message, str)
    assert len(message) > 0
    print(message)