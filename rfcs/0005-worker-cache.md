- Feature Name: `worker_cache` (MWorker Cache / If-Modified-Since Cache IMSCache)
- Start Date: 2019-02-13
- RFC PR: (leave this empty)
- Salt Issue: (leave this empty)

# Summary
[summary]: #summary

Exposing a cache instance to modules running inside a MWorker context is
desirable. A module author should be able to create/invalidate objects in a
cache at whichever granularity they desire. The cache configuration, backend,
and APIs used should be included with salt so future module authors can build
more cool things using supported APIs.


# Motivation
[motivation]: #motivation

Currently, salt has a PillarCache and plugable (salt.cache) Cache. Both caches
are TTL based.  Neither is exposed to modules, e.g. pillar, running
inside MWorker context.

For example, salt provides an interface to provide external pillar data but
does not provide a mechanism to cache the data in memory. It's expected that
external pillars produce computationally expensive and/or sizable
results.  Properly caching the result inside the MWorker process reduce load
both:
    a) inside the MWorker and
    b) at the external data source

The existing cache API solves only the latter. Using an in-memory cache instead
avoids the de/serialization (a).

A TTL Cache solves (b) but does so in such a way that it's very difficult
(borderline impossible) to ensure objects are consistent with respect to one
another.

Exposing an in-memory cache that solves both (a) and (b), an IMSCache would
greatly improve caching usefulness with regards to (a) and (b).


# Design
[design]: #detailed-design

This is the bulk of the RFC. Explain the design in enough detail for somebody familiar
with the product to understand, and for somebody familiar with the internals to implement. It should include:

- Definition of any new terminology
- Examples of how the feature is used.
- Corner-cases
- A basic code example in case the proposal involves a new or changed API
- Outline of a test plan for this feature. How do you plan to test it? Can it be automated?

## Configuration

Relevant configuration sections:

  * `worker_cache`: The cache class IMSCache, TieredIMSCache
  * `worker_cache_policy`: cache eviction policy
  * `worker_cache_tiered`: salt.cache driver to use in a tiered cache

## Exposing Cache

The MWorker creates a `worker_cache` object. The `cache` is exposed where
required, e.g. pass into `ext_pillar` function as kwarg.

## Cache API

The `worker_cache` will implement the salt.cache interface. It's possible to use
an subclass the implementation for re-use as the main salt `cache`, i.e. minion
data etc, but is out of scope for this feature.

The default `worker_cache` is an in-memory cache supporting IMS semantics. In
order to support IMS the `worker_cache` expects the load function to return
a CacheItem. When a simple object is returned instead a CacheItem will be
created and stored in the cache.

A CacheItem is a container object and should not have any functionality
```
class CacheItem(object):
    """Structure to hold metadata about cached object."""
    def __init__(self, mtime, atime, ttl, data, **extra):
        self.__version = 0 # The CacheItem version should the structure change
        self.mtime = mtime
        self.atime = atime
        self.ttl = ttl
        self.data = data
        self.extra = extra

    @classmethod
    def make(cls, mtime=0, atime=0, ttl=0, data=None, **extra)
        return cls(mtime, atime, ttl, data, **extra)
```

A CacheItem must be serializble. The caller is responsible for ensuring any
`data` or `extra` parameters can be serialized.

Not all CacheItem properties are used but are included to support different
cache policies.

IMS validation is implemented in the user-supplied load `fun` argument to
`cache`. When the key is expired the expired CacheItem is passed to the `fun`
argument; When the key is not present an empty CacheItem is passed to the `fun`.
The return value of `fun` is the updated CacheItem to store in the cache.

A special `fun` return value `None` means the key should be deleted.

### IMSCache

The reference implementation of `worker_cache` is a class IMSCache implementing
the salt.cache API. The underlying data is stored in memory. Rather than
implementing from scratch the MIT-Licensed package `cachetools` is used.

The `worker_cache_policy` provides the user some control over how objects should
be evicted. The policy should express what type of cache should be used
(LRU/LFU) and the size of the cache. IMSCache uses the policy to construct the
underlying cache store.

The `expire` argument to `cache` is supported to override the `ttl` set on the
CacheItem.


### TieredIMSCache

The TieredIMSCache stacks an IMSCache with another backing salt.cache.Cache driver.
The simple example is:

```
def cache(...):
    ...
    imscache.cache(fun=sharedcache.cache(...), ...)

def flush(...):
  sharedcache.flush(...)
  imscache.flush(...)

```

## Deprecations

The `worker_cache` does not support `loop_fun`. Attempting to pass a `loop_fun`
will raise an exception.

## Example Usage

A user can use the `worker_cache` inside `ext_pillar`

```
def ext_pillar(..., extra_minion_data):
  cache = extra_minion_data['worker_cache']
  def _get_thing():
    return "A thing"

  return cache.cache(__name__, "thing", fun=_get_thing)
```

## Testing plan

The existing salt.cache test suite will be expanded to include IMSCache
TieredIMSCache.

## Alternatives
[alternatives]: #alternatives

What other designs have been considered? What is the impact of not doing this?

### Do nothing

Exposing a cache in MWorker is a trivial change. There is no compelling reason
not to do this.

### External cache

The behavior described can be implemented using an external python module that
exposes an IMSCache Singleton. There is no strong reason not to do this other
than it would not benefit salt community/codebase as a whole.

### Completely redesign caching

Iterative improvement to existing systems should always be preferred unless the
existing design is fundamentally flawed.


## Unresolved questions
[unresolved]: #unresolved-questions

What parts of the design are still TBD?

The cache should have some strategy to prevent thundering herds (random offset
in TTL, intent locking+serve stale, etc).

Synchronization should be implemented where required.

# Drawbacks
[drawbacks]: #drawbacks

Why should we *not* do this? Please consider:

- Implementation cost, both in term of code size and complexity
- Integration of this feature with other existing and planned features
- Cost of migrating existing Salt setups (is it a breaking change?)
- Documentation (would Salt documentation need to be re-organized or altered?)

`worker_cache` introduces some new classes that are compatible with existing
interfaces. Introducing new code should be considered future debt. At some point
in the future existing and new code should be refactored to a single use. Until
we have a chance to exercise the functionality we don't know how to refactor.

The code described really doesn't have a lot of logic. The logic is implemented
externally (cachetools) or reuses existing conventions.

The code might be too simple. One `ext_pillar` might evict another pillar's
cache keys. This could be addressed by making the cache factory return the
singleton used for that particular `ext_pillar`.


