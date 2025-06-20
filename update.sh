#!/bin/bash
#
# update.sh
#
# Author: mythster (Ashir Gowardhan)
# Date Created: 2025-05-19
# Copyright 2024 mythster (Ashir Gowardhan)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
set -e

echo "--- Formatting Python code (optional)... ---"
# This step is optional and assumes 'black' is installed (pip install black)
if command -v black &> /dev/null
then
    black .
fi

echo "--- Generating latest sprint data... ---"
python jsonCreator.py

echo ""
echo "--- Local Update complete! ---"
echo "data.json has been created. Open index.html in your browser to view the dashboard."

# Once your github repository is set up, you can uncomment the following lines to commit and push changes
git add data.json style.css index.html script.js jsonCreator.py
# This will only create a commit if files have actually changed
git diff --staged --quiet || git commit -m "chore: Update sprint data"

git push

echo "--- Update complete! ---"