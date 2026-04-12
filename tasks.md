# Tasks

## Add functionality to track the status of a child worktree from a parent
This is not possible now: if I spawn a worktree, then run "mill-terminal.ps1", I cannot see the "status.md" of the child's worktree from the parent. That would have been nice. Perhaps also other relevant files. Like the reviews. 
Perhaps, for each children, add untracked junction-folder in a parent to the child's "_millhouse" folders so that we can keep track of the status. But full "millhouse" folder is perhaps a bit overkill. BUT: We CAN restructure the "_millhouse" folder a bit to better facilitatet this.

## Rewrite the plan-format to contain heavily atomic instructions
This way, a simpler, faster LLM Model can be used to implement. I think Motlin did this in his plan.


## Add Gemini CLI support for reviews
The plan herei s 