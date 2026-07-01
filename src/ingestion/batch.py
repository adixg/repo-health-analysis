BATCH_SIZE = 100


def maybe_commit_batch(session, count: int) -> None:
    if count > 0 and count % BATCH_SIZE == 0:
        session.commit()
