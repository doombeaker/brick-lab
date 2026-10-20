"""Design: storybook cottage (27 bricks), only blender-bricks unit types."""


def build(k):
    # ---------------- garden base: green 4x12 (one 4x8 + two 2x4) ----------------
    k.place("plate_4x8", 0, 0, 0, "green")
    k.place("plate_2x4", 0, 8, 0, "green")
    k.place("plate_2x4", 2, 8, 0, "green")

    # ---------------- wall layer 1: coffee door + yellow walls ----------------
    k.place("brick_2x2", 0, 2, 1, "coffee")     # front door
    k.place("brick_2x2", 2, 2, 1, "yellow")
    k.place("brick_2x6", 0, 4, 1, "yellow")
    k.place("brick_2x6", 2, 4, 1, "yellow")

    # ---------------- wall layer 2: front window + rear window ----------------
    k.place("brick_2x2", 0, 2, 4, "yellow")
    k.place("brick_2x2", 2, 2, 4, "black")      # front window
    k.place("brick_2x6", 0, 4, 4, "yellow")
    k.place("brick_2x4", 2, 4, 4, "yellow")
    k.place("brick_2x2", 2, 8, 4, "black")      # rear window

    # ---------------- gable roof: red slopes ----------------
    for y in (2, 4, 6, 8):
        k.place("slope_2x2_45", 0, y, 7, "red", rot=270)
        k.place("slope_2x2_45", 2, y, 7, "red", rot=90)

    # ---------------- chimney ----------------
    k.place("brick_1x1", 2, 6, 10, "coffee")

    # ---------------- garden details ----------------
    k.place("tile_2x2", 0, 0, 1, "gray")           # front step
    k.place("round_brick_1x1", 2, 0, 1, "orange")  # flower
    k.place("brick_2x2", 2, 10, 1, "green")        # bush at the back
