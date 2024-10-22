# Distributed under the OSI-approved BSD 3-Clause License.  See accompanying
# file Copyright.txt or https://cmake.org/licensing for details.

cmake_minimum_required(VERSION 3.5)

# If CMAKE_DISABLE_SOURCE_CHANGES is set to true and the source directory is an
# existing directory in our source tree, calling file(MAKE_DIRECTORY) on it
# would cause a fatal error, even though it would be a no-op.
if(NOT EXISTS "/Users/non-admin/Documents/GitHub/Detock/build/_deps/protobuf-src")
  file(MAKE_DIRECTORY "/Users/non-admin/Documents/GitHub/Detock/build/_deps/protobuf-src")
endif()
file(MAKE_DIRECTORY
  "/Users/non-admin/Documents/GitHub/Detock/build/_deps/protobuf-build"
  "/Users/non-admin/Documents/GitHub/Detock/build/_deps/protobuf-subbuild/protobuf-populate-prefix"
  "/Users/non-admin/Documents/GitHub/Detock/build/_deps/protobuf-subbuild/protobuf-populate-prefix/tmp"
  "/Users/non-admin/Documents/GitHub/Detock/build/_deps/protobuf-subbuild/protobuf-populate-prefix/src/protobuf-populate-stamp"
  "/Users/non-admin/Documents/GitHub/Detock/build/_deps/protobuf-subbuild/protobuf-populate-prefix/src"
  "/Users/non-admin/Documents/GitHub/Detock/build/_deps/protobuf-subbuild/protobuf-populate-prefix/src/protobuf-populate-stamp"
)

set(configSubDirs )
foreach(subDir IN LISTS configSubDirs)
    file(MAKE_DIRECTORY "/Users/non-admin/Documents/GitHub/Detock/build/_deps/protobuf-subbuild/protobuf-populate-prefix/src/protobuf-populate-stamp/${subDir}")
endforeach()
if(cfgdir)
  file(MAKE_DIRECTORY "/Users/non-admin/Documents/GitHub/Detock/build/_deps/protobuf-subbuild/protobuf-populate-prefix/src/protobuf-populate-stamp${cfgdir}") # cfgdir has leading slash
endif()
