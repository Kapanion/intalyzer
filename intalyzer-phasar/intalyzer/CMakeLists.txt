# Build a stand-alone executable
if(PHASAR_IN_TREE)
  add_phasar_executable(intalyzer
    intalyzer.cpp
  )
else()
  add_executable(intalyzer
    intalyzer.cpp
  )
endif()

target_link_libraries(intalyzer
  PUBLIC
    phasar
    ${PHASAR_STD_FILESYSTEM}
)
