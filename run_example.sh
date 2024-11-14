#!/usr/bin/env bash

# Path to GeoLinkage code
PROJECT_CODE="$HOME/flopy_test"
# Script to execute
SCRIPT_INTERFACE="CmdInterface.py"
# Default params
DEFAULT_EXAMPLE_FILE="$PROJECT_CODE/examples/demo/input_params.txt"

# call: execute_geolinkage FILE_WITH_PARAMS
execute_geolinkage(){
    FILE_WITH_PARAMS=$1
    mapfile -t <"$FILE_WITH_PARAMS"
    PARAMS=${MAPFILE[@]}
    echo "Reading example params from: $FILE_WITH_PARAMS"
    echo "Executing program: $SCRIPT_INTERFACE"
    echo "Input Params: $PARAMS"
    echo ""
    python3 CmdInterface.py $PARAMS
    echo ""
}

# call: show_use_msg FILE_WITH_PARAMS IS_DEFAULT
show_use_msg(){
  FILE=$1
  IS_DEFAULT=$2

  echo "  USE: ./run_example.sh [FILE_WITH_PARAMS_PATH]"
  echo "    (EXAMPLE 1: ./run_example.sh examples/demo/input_params.txt )"
  echo "    (EXAMPLE 2: ./run_example.sh examples/azapa/input_params_with_gw_model.txt )"
  echo "    (EXAMPLE 3: ./run_example.sh examples/azapa/input_params_without_gw_model.txt )"
  echo ""
  echo "[*] FOLDER CODE: $PROJECT_CODE"
  if [ "$IS_DEFAULT" = true ]; then
    echo "[*] Running with default file with params: $FILE"
  fi
}

# Read if exists input params file
if [ $# -eq 0 ] # not exist
  then
    FILE=$DEFAULT_EXAMPLE_FILE
    IS_DEFAULT=true
else
    FILE="$1"
    IS_DEFAULT=false
fi

# Check if file exists
if test -f "$FILE"; then
  show_use_msg "$FILE" $IS_DEFAULT
  execute_geolinkage "$FILE"
else
  FILE_PATH_ABSOLUTE="$PROJECT_CODE/$FILE"

  if test -f "$FILE_PATH_ABSOLUTE"; then
    show_use_msg "$FILE_PATH_ABSOLUTE" $IS_DEFAULT
    execute_geolinkage "$FILE_PATH_ABSOLUTE"
  else
    show_use_msg "$FILE_PATH_ABSOLUTE" $IS_DEFAULT
    echo "File not exists: $FILE"
  fi
fi


