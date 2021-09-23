from functools import partial

from boto3 import client
from cachetools import TTLCache, cached


class _HashedTuple(tuple):
    """A tuple that ensures that hash() will be called no more than once
    per element, since cache decorators will hash the key multiple
    times on a cache miss.  See also _HashedSeq in the standard
    library functools implementation.

    """

    __hashvalue = None

    def __hash__(self, hash=tuple.__hash__):
        hashvalue = self.__hashvalue
        if hashvalue is None:
            self.__hashvalue = hashvalue = hash(self)
        return hashvalue

    def __add__(self, other, add=tuple.__add__):
        return _HashedTuple(add(self, other))

    def __radd__(self, other, add=tuple.__add__):
        return _HashedTuple(add(other, self))

    def __getstate__(self):
        return {}


_kwmark = (_HashedTuple,)


def generate_hashkey(client_call, *args, **kwargs):
    kwargs = {
        **kwargs
    }
    return sum(sorted(kwargs.items()), _kwmark)


def configure_ttl_cache(maxsize=1024, ttl=600):
    cache = TTLCache(maxsize=maxsize, ttl=ttl)

    @cached(cache, key=generate_hashkey)
    def make_cached_call(client_call, *args, **kwargs) -> client:
        return client_call(**kwargs)

    return make_cached_call
