from functools import partial

from aws_lambda_powertools.utilities.typing import LambdaContext
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


def dassana_generate_hash(client_call, *args, **kwargs) -> int:
    """
    Dassana hash function used for caching AWS clients. The hash key is on service, region, and LambdaContext (if
    available). The most common case is to cache SDK clients with hashing on the service and region, and/or
    AWS credentials.

    For same-account client fetching, context is popped from **kwargs s.t hashing is done purely on the service and
    region without interfering with client creation.

    For cross-account client fetching, DassanaEngine injects AWS credentials exchanged through STS as custom env
    in LambdaContext which is concatenated as a HashTuple with service and region to generate the hash. The creds
    are unpacked as into **kwargs for hash generation (the sorting will ensure 1:1 hashing for identical objects
    regardless of key order).

    :param client_call: function
    Not involved in the hashing scheme, it is just included in generate_hash as this function is wired
    into the make_cached_call under config ure_ttl_cache.
    :param args: arguments
    :param kwargs: keyword arguments
    :return:
    """
    if issubclass(type(kwargs.get('context')), LambdaContext):
        context = dict(filter(lambda x:
                              x[0] in ['aws_access_key_id', 'aws_secret_access_key', 'aws_session_token'],
                              kwargs.pop('context').client_context.env.items()))

        kwargs = {
            **kwargs,
            **context
        }
    return sum(sorted(kwargs.items()), _kwmark).__hash__()


def configure_ttl_cache(maxsize=1024, ttl=60, hash_op=dassana_generate_hash):
    """
    Decorator that initializes a TTL Cache which is utilized in any subsequent function calls with the hashing key
    defined generate_hash. The following implementation is built as part of higher order functions to enable
    flexibility: the biggest benefit is caching can be deployed on any function calls throughout Dassana Actions whereby
    the intention / control flow can be

    :param maxsize: maximium size of the TTL cache
    :param ttl: time to live (in seconds) of items in cache
    :param hash_op: function with hashing scheme applying to the same args that make_cached_call consumes
    :return: a function with another function as its first parameter which calls on keyword arguments
             f_1(f_2(name1=value1, ..., nameN=valueN), keywords: name1=value1, name2=value2, nameN=valueN) -> f_2
    """
    cache = TTLCache(maxsize=maxsize, ttl=ttl)

    @cached(cache, key=hash_op)
    def make_cached_call(client_call, *args, **kwargs) -> client:
        return client_call(**kwargs)

    return make_cached_call
