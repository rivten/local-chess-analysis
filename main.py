import chess
import chess.pgn
import chess.engine
import io
import tqdm
import sys
import math
import enum
import pyperclip
import os

# TODO
# - logging instead of print
# - graph of the score in centipawns after the game (or in expectation)
# - using argparse properly

def games():
    while True:
        game = chess.pgn.read_game(sys.stdin)
        yield game

def get_main_player_color(headers):
    if headers['White'].lower() == os.getenv("PLAYER_NAME"):
        return chess.WHITE
    elif headers['Black'].lower() == os.getenv("PLAYER_NAME"):
        return chess.BLACK
    else:
        print("main_player not found")
        assert(False)


def get_win_percent(score, ply):
    #if type(score) is chess.engine.Mate:
    #    if score > chess.engine.Cp(0):
    #        return 1
    #    else:
    #        return 0
    #else:
    #    # taken from: https://chess.stackexchange.com/questions/41396/is-there-a-way-to-get-blunders-mistakes-and-inaccuracies-using-stockfish
    #    return 0.5 + 0.5 * ((2 / (1 + math.exp(-0.00368208 * score.score()))) - 1)
    return score.wdl(ply=ply).expectation()


class MoveAssessment(enum.Enum):
    NONE = 0
    BLUNDER = 1
    MISTAKE = 2

def get_move_assessment(score_before, score_after, ply):
    win_percent_before = get_win_percent(score_before, ply - 1)
    win_percent_after = get_win_percent(score_after, ply)
    win_percent_change = win_percent_after - win_percent_before

    win_percent_change_abs = abs(win_percent_change)

    if win_percent_change_abs > 0.2:
        return MoveAssessment.BLUNDER
    elif win_percent_change_abs > 0.1:
        return MoveAssessment.MISTAKE
    else:
        return MoveAssessment.NONE

def lichess_fen(fen, main_player_color):
    return f'https://lichess.org/analysis/{fen.replace(" ", "_")}?color={"white" if main_player_color == chess.WHITE else "black"}'

def analyze_game(game, engine):
    print(game.headers)
    main_player_color = get_main_player_color(game.headers)
    print("main_player is white ?", main_player_color)

    board = game.board()
    score_before_my_turn = chess.engine.Cp(0)
    score_after_my_turn = chess.engine.Cp(0)
    #for move in tqdm.tqdm(list(game.mainline_moves())):
    for ply, move in enumerate(game.mainline_moves()):
        san_move = board.san(move)
        if ply % 2 == 0:
            print(f'{int(ply / 2) + 1}.{san_move}')
        else:
            print(f'{int(ply / 2) + 1}..{san_move}')
        fen = board.fen()
        board.push(move)
        engine_eval_result = engine.play(board, chess.engine.Limit(depth=24), info = chess.engine.Info.SCORE)
        score = engine_eval_result.info['score'].pov(main_player_color)
        #print('Score is', score)
        if board.turn == main_player_color:
            # my opponent just played
            score_before_my_turn = score
        else:
            # i just played
            score_after_my_turn = score
            move_assessment = get_move_assessment(score_before_my_turn, score_after_my_turn, ply + 1)
            if move_assessment == MoveAssessment.BLUNDER:
                print("blunder")
                print(fen)
                print(lichess_fen(fen, main_player_color))
                print(f"Move {san_move} was played in this position")
                #blunders.append({
                #    "game": game,
                #    "ply": ply,
                #    "fen": fen,
                #    "score_before": score_before_my_turn,
                #    "score_after": score_after_my_turn,
                #    "move_san_played": san_move,
                #})
                #print(blunders)
            elif move_assessment == MoveAssessment.MISTAKE:
                print("mistake")
                print(fen)
                print(lichess_fen(fen, main_player_color))
                print(f"Move {san_move} was played in this position")

if __name__ == "__main__":
    engine = chess.engine.SimpleEngine.popen_uci('stockfish')
    engine.configure({'Threads': '3'})
    blunders = []
    paste = pyperclip.paste()
    if paste == "":
        for game in games():
            analyze_game(game, engine)
    else:
        raw_game = io.StringIO(paste)
        game = chess.pgn.read_game(raw_game)
        analyze_game(game, engine)


    engine.quit()
