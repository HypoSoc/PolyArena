# PolyArena

A script aid for a mafia-inpired forum game I run. More of a 'for fun' coding project than anything serious or clean. Beware the spaghetti.

I might eventually convert this into a fuly automated game with a UI, but for now I am just building something to handle all the mechanics.

# Downloading:
`git clone https://github.com/HypoSoc/PolyArena.git`

`cd PolyArena`

This will create a folder called PolyArena in your current repository, and move into it. 

# Installing the dependencies: 
`python -m pip install pyyaml`

# Running:
`python main.py`

# Writing the code:
In the main.py code, after `if __name__ == '__main__':` : 
- To load a game: `load(YEARNAME)` to load the last save of YEARNAME, or `load(YEARNNAME, turn=TURN, night=True/False)` to load a specific turn.
- To launch a game: `init()`
- To save a game: at the very end of the block, `GAME.save(YEARNAME)`