```
**Project Document Link:** https://docs.google.com/document/d/1VlHirN62sWE1CwXr4v2YM40sg8luskD6VY4A2gKOHK4/edit?usp=sharing
```
automated-research-report-generation 

uv --version

uv venv --python 3.11

uv init automated-research-report-generation

uv add -r requirements.txt ## use if venv not added

uv pip install -r requirements.txt

uv python list

uv pip freeze > requirements.txt && uv sync --active
 # adding requirement to update project.toml
uv add --requirements requirements.txt


# Multi-agent

Create a supervisor connected with worker


Agentic Workflow > 


# remove rested dire


# Git
git add .
git remote add origin https://github.com/supriyo100/repogen.git
git branch -M main

# Create ssh key
ssh-keygen -t ed25519 -C "ryugan01@gmail.com"

# copy the key 
cat ~/.ssh/id_ed25519.pub

# set ssh in Github
https://github.com/settings/keys

# Set remote origin
git remote set-url origin git@github.com:supriyo100/repogen.git

# Check git remote
git remote -v

# Authenticate with github
ssh -T git@github.com

# push to git main
git push -u origin main

git remote set-url origin git@github.com:supriyo100/repogen.git

git pull origin main --rebase
