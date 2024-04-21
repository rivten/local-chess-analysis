import chess
import chess.pgn
import chess.engine
import io
import tomllib
import tqdm
import sys
import math
import enum
import pyperclip
import os
import matplotlib.pyplot as plt
import csv

# TODO
# - logging instead of print
# - using argparse properly


with open("config.toml", "rb") as f:
    config = tomllib.load(f)

print(config)

def games():
    while True:
        game = chess.pgn.read_game(sys.stdin)
        yield game

def get_main_player_color(headers):
    color = input("Which color to analyze ? [w/b]")
    if color.lower().startswith("w"):
        return chess.WHITE
    elif color.lower().startswith("b"):
        return chess.BLACK
    else:
        print("main_player not found")
        assert(False)
    #if headers['White'].lower() == config["player_name"]:
    #    return chess.WHITE
    #elif headers['Black'].lower() == config["player_name"]:
    #    return chess.BLACK
    #else:
    #    print("main_player not found")
    #    assert(False)


def get_win_percent(score, ply):
    #if type(score) is chess.engine.Mate:
    #    if score > chess.engine.Cp(0):
    #        return 1
    #    else:
    #        return 0
    #else:
    #    # taken from: https://chess.stackexchange.com/questions/41396/is-there-a-way-to-get-blunders-mistakes-and-inaccuracies-using-stockfish
    #    return 0.5 + 0.5 * ((2 / (1 + math.exp(-0.00368208 * score.score()))) - 1)
    return score.wdl(model=config["wdl_model"], ply=ply).expectation()


class MoveAssessment(enum.Enum):
    NONE = 0
    BLUNDER = 1
    MISTAKE = 2

def get_move_assessment(score_before, score_after, ply):
    win_percent_before = get_win_percent(score_before, ply - 1)
    win_percent_after = get_win_percent(score_after, ply)
    win_percent_change = win_percent_after - win_percent_before

    if win_percent_change < -0.2:
        return MoveAssessment.BLUNDER
    elif win_percent_change < -0.1:
        return MoveAssessment.MISTAKE
    else:
        return MoveAssessment.NONE

def lichess_fen(fen, main_player_color):
    return f'https://lichess.org/analysis/{fen.replace(" ", "_")}?color={"white" if main_player_color == chess.WHITE else "black"}'

# TODO: figure out why there is a +1 and +2 here
def beautiful_san_move(san, ply):
    if ply % 2 == 0:
        return f'{int(ply / 2) + 1}..{san}'
    else:
        return f'{int(ply / 2) + 2}.{san}'

def lichess_analysis_full(game):
    exporter = chess.pgn.StringExporter(headers=False, variations=False, comments=False)
    game_url = game.accept(exporter).replace("*", "").replace(" ", "%20").replace("\n", "%20")
    return f'https://lichess.org/paste?pgn={game_url}'

def analyze_game(game, engine):
    print(game.headers)
    main_player_color = get_main_player_color(game.headers)
    #if config["color"] is None:
    #    main_player_color = get_main_player_color(game.headers)
    #else:
    #    if config["color"] == "white":
    #        main_player_color = chess.WHITE
    #    elif config["color"] == "black":
    #        main_player_color = chess.BLACK
    print("main_player is white ?", main_player_color)

    win_percent_data = []
    annotations = []
    csv_data = []

    board = game.board()
    score_before_my_turn = chess.engine.Cp(0)
    score_after_my_turn = chess.engine.Cp(0)
    print(lichess_analysis_full(game))
    for ply, move in tqdm.tqdm(list(enumerate(game.mainline_moves()))):
        san_move = board.san(move)
        #if ply % 2 == 0:
        #    print(f'{int(ply / 2) + 1}.{san_move}')
        #else:
        #    print(f'{int(ply / 2) + 1}..{san_move}')
        fen = board.fen()
        board.push(move)
        engine_eval_result = engine.play(board, chess.engine.Limit(depth=config["stockfish_depth"]), info = chess.engine.Info.SCORE)
        score = engine_eval_result.info['score'].pov(main_player_color)
        win_percent = get_win_percent(score, ply+1)
        win_percent_data.append(win_percent)
        csv_data.append((ply, win_percent))
        #print('Score is', score)
        if board.turn == main_player_color:
            # my opponent just played
            score_before_my_turn = score
        else:
            # i just played
            score_after_my_turn = score
            move_assessment = get_move_assessment(score_before_my_turn, score_after_my_turn, ply + 1)
            if move_assessment != MoveAssessment.NONE:
                annotations.append(
                    {
                        "type": "blunder" if move_assessment == MoveAssessment.BLUNDER else "mistake",
                        "ply": ply - 1,
                        "san": san_move,
                        "win%": get_win_percent(score_before_my_turn, ply),
                        "fen": fen,
                    }
                )
            #if move_assessment == MoveAssessment.BLUNDER:
            #    print("blunder")
            #    print(fen)
            #    print(lichess_fen(fen, main_player_color))
            #    print(f"Move {san_move} was played in this position")
            #    #blunders.append({
            #    #    "game": game,
            #    #    "ply": ply,
            #    #    "fen": fen,
            #    #    "score_before": score_before_my_turn,
            #    #    "score_after": score_after_my_turn,
            #    #    "move_san_played": san_move,
            #    #})
            #    #print(blunders)
            #elif move_assessment == MoveAssessment.MISTAKE:
            #    print("mistake")
            #    print(fen)
            #    print(lichess_fen(fen, main_player_color))
            #    print(f"Move {san_move} was played in this position")
    #print(win_percent_data)
    #with open("game_analysis.csv", "w") as csvfile:
    #    writer = csv.writer(csvfile)
    #    for s in save:
    #        writer.writerow((str(s[0]), str(s[1])))
    with open("plot.csv", "w") as csvfile:
        writer = csv.writer(csvfile)
        for s in csv_data:
            writer.writerow(s)

    for annotation in annotations:
        print(f'{beautiful_san_move(annotation["san"], annotation["ply"])}:{annotation["type"]}: {lichess_fen(annotation["fen"], main_player_color)}')
    plt.plot(win_percent_data)
    plt.scatter(
        [annotation['ply'] for annotation in annotations if annotation['type'] == 'blunder'],
        [annotation['win%'] for annotation in annotations if annotation['type'] == 'blunder'],
        c='r',
    )
    plt.scatter(
        [annotation['ply'] for annotation in annotations if annotation['type'] == 'mistake'],
        [annotation['win%'] for annotation in annotations if annotation['type'] == 'mistake'],
        c='orange',
    )
    for annotation in annotations:
        plt.annotate(beautiful_san_move(annotation['san'], annotation['ply']), (annotation['ply'], annotation['win%']))
    plt.axhline(y = 0.5, color = 'black', linestyle='-')
    ax = plt.gca()
    ax.set_ylim([0.0, 1.0])
    plt.show()


if __name__ == "__main__":
    engine = chess.engine.SimpleEngine.popen_uci(config["stockfish_path"])
    engine.configure({'Threads': os.getenv("STOCKFISH_THREADS", config["stockfish_threads"])})
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
