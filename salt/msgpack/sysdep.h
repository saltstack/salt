/*
 * MessagePack system dependencies
 *
 * Copyright (C) 2008-2009 FURUHASHI Sadayuki
 *
 *    Licensed under the Apache License, Version 2.0 (the "License");
 *    you may not use this file except in compliance with the License.
 *    You may obtain a copy of the License at
 *
 *        http://www.apache.org/licenses/LICENSE-2.0
 *
 *    Unless required by applicable law or agreed to in writing, software
 *    distributed under the License is distributed on an "AS IS" BASIS,
 *    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *    See the License for the specific language governing permissions and
 *    limitations under the License.
 */
#ifndef MSGPACK_SYSDEP_H__
#define MSGPACK_SYSDEP_H__


#ifdef _MSC_VER
typedef __int8 int8_t;
typedef unsigned __int8 uint8_t;
typedef __int16 int16_t;
typedef unsigned __int16 uint16_t;
typedef __int32 int32_t;
typedef unsigned __int32 uint32_t;
typedef __int64 int64_t;
typedef unsigned __int64 uint64_t;
#else
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#endif


#ifdef _WIN32
typedef long _msgpack_atomic_counter_t;
#define _msgpack_sync_decr_and_fetch(ptr) InterlockedDecrement(ptr)
#define _msgpack_sync_incr_and_fetch(ptr) InterlockedIncrement(ptr)
#else
typedef unsigned int _msgpack_atomic_counter_t;
#define _msgpack_sync_decr_and_fetch(ptr) __sync_sub_and_fetch(ptr, 1)
#define _msgpack_sync_incr_and_fetch(ptr) __sync_add_and_fetch(ptr, 1)
#endif


#ifdef _WIN32
#include <winsock2.h>
#else
#include <arpa/inet.h>  /* __BYTE_ORDER */
#endif

#if !defined(__LITTLE_ENDIAN__) && !defined(__BIG_ENDIAN__)
#if __BYTE_ORDER == __LITTLE_ENDIAN
#define __LITTLE_ENDIAN__
#elif __BYTE_ORDER == __BIG_ENDIAN
#define __BIG_ENDIAN__
#endif
#endif

#ifdef __LITTLE_ENDIAN__

#define _msgpack_be16(x) ntohs(x)
#define _msgpack_be32(x) ntohl(x)

#if defined(_byteswap_uint64)
#  define _msgpack_be64(x) (_byteswap_uint64(x))
#elif defined(bswap_64)
#  define _msgpack_be64(x) bswap_64(x)
#elif defined(__DARWIN_OSSwapInt64)
#  define _msgpack_be64(x) __DARWIN_OSSwapInt64(x)
#else
#define _msgpack_be64(x) \
	( ((((uint64_t)x) << 56) & 0xff00000000000000ULL ) | \
	  ((((uint64_t)x) << 40) & 0x00ff000000000000ULL ) | \
	  ((((uint64_t)x) << 24) & 0x0000ff0000000000ULL ) | \
	  ((((uint64_t)x) <<  8) & 0x000000ff00000000ULL ) | \
	  ((((uint64_t)x) >>  8) & 0x00000000ff000000ULL ) | \
	  ((((uint64_t)x) >> 24) & 0x0000000000ff0000ULL ) | \
	  ((((uint64_t)x) >> 40) & 0x000000000000ff00ULL ) | \
	  ((((uint64_t)x) >> 56) & 0x00000000000000ffULL ) )
#endif

#else
#define _msgpack_be16(x) (x)
#define _msgpack_be32(x) (x)
#define _msgpack_be64(x) (x)
#endif


#endif /* msgpack/sysdep.h */

