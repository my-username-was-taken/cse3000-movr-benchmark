if(EXISTS "/Users/non-admin/Documents/GitHub/Detock/build/test/log_manager_test[1]_tests.cmake")
  include("/Users/non-admin/Documents/GitHub/Detock/build/test/log_manager_test[1]_tests.cmake")
else()
  add_test(log_manager_test_NOT_BUILT log_manager_test_NOT_BUILT)
endif()
