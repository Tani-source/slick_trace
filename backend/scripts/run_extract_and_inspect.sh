#!/bin/bash
set -e

echo "Waiting for Part III download (task-875) to finish..."
while ps aux | grep -v grep | grep "02_Test_images_and_ground_truth.7z" > /dev/null; do
    sleep 5
done

echo "Part III download finished!"
ls -lh /Users/tanishkotian/slick_trace/downloads/02_Test_images_and_ground_truth.7z

echo "Extracting Part III archive..."
mkdir -p /Users/tanishkotian/slick_trace/downloads/extracted_part3
/opt/homebrew/bin/7zz x -y /Users/tanishkotian/slick_trace/downloads/02_Test_images_and_ground_truth.7z -o/Users/tanishkotian/slick_trace/downloads/extracted_part3

echo "Organizing files into backend/data/real/sar/..."
/Library/Frameworks/Python.framework/Versions/3.13/bin/python3 /Users/tanishkotian/slick_trace/backend/scripts/organize_real_data.py /Users/tanishkotian/slick_trace/downloads/extracted_part3 /Users/tanishkotian/slick_trace/backend/data/real/sar

echo "Running inspect_real_data.py..."
KMP_DUPLICATE_LIB_OK=TRUE /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 /Users/tanishkotian/slick_trace/backend/scripts/inspect_real_data.py /Users/tanishkotian/slick_trace/backend/data/real/sar

echo "ALL_DONE_SUCCESSFULLY"
