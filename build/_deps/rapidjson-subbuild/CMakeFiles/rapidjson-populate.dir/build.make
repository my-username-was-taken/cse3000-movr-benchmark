# CMAKE generated file: DO NOT EDIT!
# Generated by "Unix Makefiles" Generator, CMake Version 3.30

# Delete rule output on recipe failure.
.DELETE_ON_ERROR:

#=============================================================================
# Special targets provided by cmake.

# Disable implicit rules so canonical targets will work.
.SUFFIXES:

# Disable VCS-based implicit rules.
% : %,v

# Disable VCS-based implicit rules.
% : RCS/%

# Disable VCS-based implicit rules.
% : RCS/%,v

# Disable VCS-based implicit rules.
% : SCCS/s.%

# Disable VCS-based implicit rules.
% : s.%

.SUFFIXES: .hpux_make_needs_suffix_list

# Command-line flag to silence nested $(MAKE).
$(VERBOSE)MAKESILENT = -s

#Suppress display of executed commands.
$(VERBOSE).SILENT:

# A target that is always out of date.
cmake_force:
.PHONY : cmake_force

#=============================================================================
# Set environment variables for the build.

# The shell in which to execute make rules.
SHELL = /bin/sh

# The CMake executable.
CMAKE_COMMAND = /opt/homebrew/Cellar/cmake/3.30.3/bin/cmake

# The command to remove a file.
RM = /opt/homebrew/Cellar/cmake/3.30.3/bin/cmake -E rm -f

# Escaping for special characters.
EQUALS = =

# The top-level source directory on which CMake was run.
CMAKE_SOURCE_DIR = /Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-subbuild

# The top-level build directory on which CMake was run.
CMAKE_BINARY_DIR = /Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-subbuild

# Utility rule file for rapidjson-populate.

# Include any custom commands dependencies for this target.
include CMakeFiles/rapidjson-populate.dir/compiler_depend.make

# Include the progress variables for this target.
include CMakeFiles/rapidjson-populate.dir/progress.make

CMakeFiles/rapidjson-populate: CMakeFiles/rapidjson-populate-complete

CMakeFiles/rapidjson-populate-complete: rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-install
CMakeFiles/rapidjson-populate-complete: rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-mkdir
CMakeFiles/rapidjson-populate-complete: rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-download
CMakeFiles/rapidjson-populate-complete: rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-update
CMakeFiles/rapidjson-populate-complete: rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-patch
CMakeFiles/rapidjson-populate-complete: rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-configure
CMakeFiles/rapidjson-populate-complete: rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-build
CMakeFiles/rapidjson-populate-complete: rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-install
CMakeFiles/rapidjson-populate-complete: rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-test
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --blue --bold --progress-dir=/Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-subbuild/CMakeFiles --progress-num=$(CMAKE_PROGRESS_1) "Completed 'rapidjson-populate'"
	/opt/homebrew/Cellar/cmake/3.30.3/bin/cmake -E make_directory /Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-subbuild/CMakeFiles
	/opt/homebrew/Cellar/cmake/3.30.3/bin/cmake -E touch /Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-subbuild/CMakeFiles/rapidjson-populate-complete
	/opt/homebrew/Cellar/cmake/3.30.3/bin/cmake -E touch /Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-subbuild/rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-done

rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-update:
.PHONY : rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-update

rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-build: rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-configure
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --blue --bold --progress-dir=/Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-subbuild/CMakeFiles --progress-num=$(CMAKE_PROGRESS_2) "No build step for 'rapidjson-populate'"
	cd /Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-build && /opt/homebrew/Cellar/cmake/3.30.3/bin/cmake -E echo_append
	cd /Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-build && /opt/homebrew/Cellar/cmake/3.30.3/bin/cmake -E touch /Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-subbuild/rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-build

rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-configure: rapidjson-populate-prefix/tmp/rapidjson-populate-cfgcmd.txt
rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-configure: rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-patch
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --blue --bold --progress-dir=/Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-subbuild/CMakeFiles --progress-num=$(CMAKE_PROGRESS_3) "No configure step for 'rapidjson-populate'"
	cd /Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-build && /opt/homebrew/Cellar/cmake/3.30.3/bin/cmake -E echo_append
	cd /Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-build && /opt/homebrew/Cellar/cmake/3.30.3/bin/cmake -E touch /Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-subbuild/rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-configure

rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-download: rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-gitinfo.txt
rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-download: rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-mkdir
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --blue --bold --progress-dir=/Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-subbuild/CMakeFiles --progress-num=$(CMAKE_PROGRESS_4) "Performing download step (git clone) for 'rapidjson-populate'"
	cd /Users/non-admin/Documents/GitHub/Detock/build/_deps && /opt/homebrew/Cellar/cmake/3.30.3/bin/cmake -DCMAKE_MESSAGE_LOG_LEVEL=VERBOSE -P /Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-subbuild/rapidjson-populate-prefix/tmp/rapidjson-populate-gitclone.cmake
	cd /Users/non-admin/Documents/GitHub/Detock/build/_deps && /opt/homebrew/Cellar/cmake/3.30.3/bin/cmake -E touch /Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-subbuild/rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-download

rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-install: rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-build
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --blue --bold --progress-dir=/Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-subbuild/CMakeFiles --progress-num=$(CMAKE_PROGRESS_5) "No install step for 'rapidjson-populate'"
	cd /Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-build && /opt/homebrew/Cellar/cmake/3.30.3/bin/cmake -E echo_append
	cd /Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-build && /opt/homebrew/Cellar/cmake/3.30.3/bin/cmake -E touch /Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-subbuild/rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-install

rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-mkdir:
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --blue --bold --progress-dir=/Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-subbuild/CMakeFiles --progress-num=$(CMAKE_PROGRESS_6) "Creating directories for 'rapidjson-populate'"
	/opt/homebrew/Cellar/cmake/3.30.3/bin/cmake -Dcfgdir= -P /Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-subbuild/rapidjson-populate-prefix/tmp/rapidjson-populate-mkdirs.cmake
	/opt/homebrew/Cellar/cmake/3.30.3/bin/cmake -E touch /Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-subbuild/rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-mkdir

rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-patch: rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-patch-info.txt
rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-patch: rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-update
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --blue --bold --progress-dir=/Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-subbuild/CMakeFiles --progress-num=$(CMAKE_PROGRESS_7) "No patch step for 'rapidjson-populate'"
	/opt/homebrew/Cellar/cmake/3.30.3/bin/cmake -E echo_append
	/opt/homebrew/Cellar/cmake/3.30.3/bin/cmake -E touch /Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-subbuild/rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-patch

rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-update:
.PHONY : rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-update

rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-test: rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-install
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --blue --bold --progress-dir=/Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-subbuild/CMakeFiles --progress-num=$(CMAKE_PROGRESS_8) "No test step for 'rapidjson-populate'"
	cd /Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-build && /opt/homebrew/Cellar/cmake/3.30.3/bin/cmake -E echo_append
	cd /Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-build && /opt/homebrew/Cellar/cmake/3.30.3/bin/cmake -E touch /Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-subbuild/rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-test

rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-update: rapidjson-populate-prefix/tmp/rapidjson-populate-gitupdate.cmake
rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-update: rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-update-info.txt
rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-update: rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-download
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --blue --bold --progress-dir=/Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-subbuild/CMakeFiles --progress-num=$(CMAKE_PROGRESS_9) "Performing update step for 'rapidjson-populate'"
	cd /Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-src && /opt/homebrew/Cellar/cmake/3.30.3/bin/cmake -Dcan_fetch=YES -DCMAKE_MESSAGE_LOG_LEVEL=VERBOSE -P /Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-subbuild/rapidjson-populate-prefix/tmp/rapidjson-populate-gitupdate.cmake

rapidjson-populate: CMakeFiles/rapidjson-populate
rapidjson-populate: CMakeFiles/rapidjson-populate-complete
rapidjson-populate: rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-build
rapidjson-populate: rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-configure
rapidjson-populate: rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-download
rapidjson-populate: rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-install
rapidjson-populate: rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-mkdir
rapidjson-populate: rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-patch
rapidjson-populate: rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-test
rapidjson-populate: rapidjson-populate-prefix/src/rapidjson-populate-stamp/rapidjson-populate-update
rapidjson-populate: CMakeFiles/rapidjson-populate.dir/build.make
.PHONY : rapidjson-populate

# Rule to build all files generated by this target.
CMakeFiles/rapidjson-populate.dir/build: rapidjson-populate
.PHONY : CMakeFiles/rapidjson-populate.dir/build

CMakeFiles/rapidjson-populate.dir/clean:
	$(CMAKE_COMMAND) -P CMakeFiles/rapidjson-populate.dir/cmake_clean.cmake
.PHONY : CMakeFiles/rapidjson-populate.dir/clean

CMakeFiles/rapidjson-populate.dir/depend:
	cd /Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-subbuild && $(CMAKE_COMMAND) -E cmake_depends "Unix Makefiles" /Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-subbuild /Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-subbuild /Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-subbuild /Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-subbuild /Users/non-admin/Documents/GitHub/Detock/build/_deps/rapidjson-subbuild/CMakeFiles/rapidjson-populate.dir/DependInfo.cmake "--color=$(COLOR)"
.PHONY : CMakeFiles/rapidjson-populate.dir/depend

