For this project in this directory, complete the following task using the information you found in this directory only and from the user message. Do not go into _TESTING, _LOGS or _ARCHIVED, _LOCAL_FILES, these are not files for you to see.

## Task
1. Review the current CLAUDE.md, you must keep what is in there and slightly customize it for this project following the instructions in it at the top.
2. Use the the info in _STARTHERE/INSTRUCTIONS.md,  _STARTHERE/PROJECT_INFO and your research of the directory to create/update the vision document explaining what this will be. If there are already files and folders in the project, use that for context. But listen to what the user tells you about the big picture and a vision which will have more weight for the vision documentation. Ensure you do not go in  _TESTING, _LOGS or _ARCHIVED, _LOCAL_FILES.
3. If the directory/project has already started, then review it and create/update the ARCHITECTURE.md with the planned or current architecture. Do not make up info do just what you know as of now. This will be updated on ongoing.
4. Ignore the RULES.md file.
5. Go back to _STARTHERE/MCP_SETUP and setup the MCP servers using the info inside this folder. Test your MCP servers to make sure they work. Set them up if not or tell the user if they don't. Also test your hooks to make sure they are doing what they're supposed to do. If not tell your user. Set up the MCP servers yourself you on on the terminal. First check if the MCP is here already first. If not, then you do it. All of the credentials for the MCPs will be in the folders.
6. Go back to _STARTHERE/DCG_SETUP and setup the MCP servers using the info inside this folder
7. Go back to _STARTHERE/GITHUB_SETUP and setup GITHUB using the CLI and in the info inside this folder. Commit and push to github
8. Then return back to the user and tell them any problems you couldn't solve, and a checklist of what's been completed and not completed.

---

## CLAUDE.md Template

### Directory Standards
- **_ARCHIVED** - Do not access this folder. Archived files with no access permissions.
- **_TESTING** - All testing scripts go here. Keep production directory clean - only production-approved scripts in main directory.
- **_LOGS** - All log documents go here.
- **_LOCAL_FILES** - If we have any scripts that save data locally before inserting it into the database, this is where it will go. You will create subdirectories for each pipeline.
- **AGENT_KNOWLEDGE**
  - **docs/** - Project documentation library. Reference when stuck.
  - **RULES.md** - Bullet point rules to follow for this directory.
  - **ARCHITECTURE.md** - High-level architecture and workflow explanations.
  - **VISION.md** - Future build vision and roadmap.


This is not the time for you to create a plan for the project. Right now you're just getting the project set up for the user and the AI to work together. Once the project is set up, everything is tested, I will then tell you to plan. 