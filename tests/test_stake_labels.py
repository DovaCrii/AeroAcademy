from apps.progress.external import distinct_stake_labels, stake_label


def test_stake_labels_distinguish_courses_that_share_their_start():
    titles = [
        "Bentley Accredited MicroStation User",
        "MicroStation Basics",
        "MicroStation 3D Modeling, Rendering, and Animation",
        "Introduction to the MicroStation Python Editor",
        "AccuDraw Minutes with MicroStation",
    ]
    labels = distinct_stake_labels(titles, 9)
    assert labels == ["User", "Basics", "3D Model…", "Python E…", "AccuDraw…"]
    assert len(set(labels)) == len(labels)


def test_stake_labels_use_the_tail_when_one_title_extends_another():
    titles = ["Using Terrain in MicroStation", "Using Terrain in MicroStation CONNECT Edition"]
    labels = distinct_stake_labels(titles, 9)
    assert labels[0] != labels[1]
    assert labels[1].startswith("CONNECT")


def test_stake_labels_leave_unique_starts_alone():
    titles = ["Navigating Bentley Learn", "Road Modeler Core"]
    assert distinct_stake_labels(titles, 20) == [stake_label(t, 20) for t in titles]
