if(EXISTS "/Users/non-admin/Documents/GitHub/Detock/build/test/mem_only_storage_test[1]_tests.cmake")
  include("/Users/non-admin/Documents/GitHub/Detock/build/test/mem_only_storage_test[1]_tests.cmake")
else()
  add_test(mem_only_storage_test_NOT_BUILT mem_only_storage_test_NOT_BUILT)
endif()
