"""Design: 2-wide destroyer (26 bricks), only blender-bricks unit types."""


def build(k):
    # ---------------- hull ----------------
    for y in (0, 6, 12, 18):
        k.place("brick_2x6", 0, y, 0, "red")          # red bottom
    k.place("slope_2x2_45", 0, 0, 3, "gray", rot=0)   # raked bow
    k.place("brick_2x4", 0, 2, 3, "gray")
    k.place("brick_2x6", 0, 6, 3, "gray")
    k.place("brick_2x6", 0, 12, 3, "gray")
    k.place("brick_2x4", 0, 18, 3, "gray")
    k.place("slope_2x2_45", 0, 22, 3, "gray", rot=180)  # stern

    # ---------------- deck ----------------
    for y in (2, 6, 10, 14, 18):
        k.place("plate_2x4", 0, y, 6, "gray")

    # ---------------- superstructure ----------------
    k.place("brick_2x2", 0, 4, 7, "gray")             # forward turret
    k.place("brick_1x1", 0, 3, 7, "gray")             # twin gun barrels
    k.place("brick_1x1", 1, 3, 7, "gray")

    k.place("brick_2x2", 0, 9, 7, "gray")             # bridge
    k.place("brick_2x2", 0, 9, 10, "gray")            # bridge upper deck
    k.place("round_brick_1x1", 1, 10, 13, "black")    # mast

    k.place("round_brick_1x1", 1, 13, 7, "black")     # funnel
    k.place("round_brick_1x1", 1, 13, 10, "black")    # funnel upper

    k.place("brick_2x2", 0, 16, 7, "gray")            # aft turret
    k.place("brick_1x1", 0, 18, 7, "gray")            # aft gun barrels
    k.place("brick_1x1", 1, 18, 7, "gray")
