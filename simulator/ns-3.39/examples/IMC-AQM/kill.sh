#!/bin/bash
xx=$1
yy=$2

ps -ef | grep "$yy" | grep "$xx"

if [ "$#" -eq 3 ]; then
    kill=$3
    kill -9 $(ps -ef | grep "$yy" | grep "$xx"| awk '{print $2}')
fi
