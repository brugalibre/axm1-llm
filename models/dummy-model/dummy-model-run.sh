#!/bin/bash
# Print the initial messages with latency
echo "LLM init start"
sleep 4
echo "LLM init ok"
sleep 2
echo "Type q to exit"
# Read from stdin in a loop
while true; do
  read -r user_input
  if [[ "$user_input" == "q" || "$user_input" == "Q" ]]; then
    break
  fi
  sleep 2
  echo "<think>Alright user asked me a very important question. How should I response?"
  sleep 2
  echo "Mhh tough question, Thats going to take som time"
  sleep 2
  echo "Allright, I guess I have it"
  sleep 2
  echo "The answer is 45"
  sleep 2
  echo "No wait, thats crap. The answer is: hallelujah"
  sleep 2
  echo "Nope! wait, ok I've got it: My final answer is </think> The answer is 42: $user_input"
  echo "hit eos,avg 4.22 token/s"
done