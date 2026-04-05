# millhouse

## Backlog

### Flytt worktree-config fra _helm/config.yaml til _git/config.yaml [backlog]

- priority: high
    ```md
    worktree.branch-template og worktree.path-template hører til git-pluginen, ikke helm. Flytt dem til _git/config.yaml og oppdater alle helm-scripts og skills som leser disse verdiene (helm-spawn, helm-merge, helm-setup, etc.).
    ```
    
### git /git-pr skill

    ```md
    Merge arbeidsbranch til main. Pull origin/main inn i nåværende branch, resolve conflicts, verifiser, push. Privat repo: direct squash merge til main. Jobb-repo: lag PR. Etter merge: slett arbeidsbranchen og lag ny fra oppdatert main (reset). Config: require-pr-for-main true/false i _helm/config.yaml.
    ```

### Finn bedre kanban-extension

    ```md
    kanban.md krever manuell lagring, popper opp filer, og har begrenset metadata-støtte. Finn eller bygg noe bedre.
    ```

## Spawn

## Delete
