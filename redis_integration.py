import redis

r = redis.Redis(host="localhost", port=6379, decode_responses=True)


def upvote(answer_id, voter_id, author_name):
    # SADD returns 0 if this voter is already in the set
    if not r.sadd(f"answer:{answer_id}:voters", str(voter_id)):
        return False
    r.incr(f"answer:{answer_id}:votes")
    r.zincrby("leaderboard", 1, author_name)
    return True


def get_votes(answer_id):
    return int(r.get(f"answer:{answer_id}:votes") or 0)


def leaderboard(n=10):
    return r.zrevrange("leaderboard", 0, n - 1, withscores=True)