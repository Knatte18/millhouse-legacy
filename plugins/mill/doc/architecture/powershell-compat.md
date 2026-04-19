# PowerShell 5.1 Compatibility

Pitfalls when writing scripts that must run on PowerShell 5.1 (Windows built-in).

## Join-Path with 3+ arguments

`Join-Path` accepts multiple child-path arguments only in PowerShell 7+. On 5.1, the third argument is rejected as an unknown positional parameter.

```powershell
# Broken on PS 5.1:
$path = Join-Path $root ".millhouse" "git"

# Fix — nest the calls:
$path = Join-Path (Join-Path $root ".millhouse") "git"

# Alternative — pipeline chaining (also works on 5.1):
$path = Join-Path $root ".millhouse" | Join-Path -ChildPath "git"
```

### Misleading error with CmdletBinding

If the script uses `[CmdletBinding()] param()`, PowerShell 5.1 reports the error as a **script parameter binding failure** rather than pointing to the `Join-Path` call:

```
fetch-issues.ps1 : A positional parameter cannot be found that accepts argument 'git'.
```

This makes it look like `'git'` is being passed to the script itself. Remove `[CmdletBinding()]` temporarily to see the real error location.
