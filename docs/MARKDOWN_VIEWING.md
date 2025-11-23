# Markdown Viewing Guide

## Quick Options

### 1. Using `glow` (Recommended - Beautiful Terminal Rendering)

**Install:**
```bash
# RHEL/Rocky/CentOS
sudo dnf install glow

# Or via Go
go install github.com/charmbracelet/glow@latest
```

**Use:**
```bash
# View a file
glow README.md
glow docs/GETTING_STARTED.md

# Interactive browser mode
glow docs/

# Pager mode (like less)
glow -p README.md
```

### 2. Using `bat` (Syntax Highlighting)

**Install:**
```bash
sudo dnf install bat
```

**Use:**
```bash
bat --style=plain --language=markdown README.md
bat -p docs/CONFIGURATION.md  # Plain style
```

### 3. Using `mdless` (Markdown Pager)

**Install:**
```bash
gem install mdless
```

**Use:**
```bash
mdless README.md
mdless docs/ARCHITECTURE.md
```

### 4. Using `less` (Built-in, No Markdown Rendering)

**Use:**
```bash
less README.md
less -R docs/TROUBLESHOOTING.md  # -R for ANSI colors
```

### 5. Using `cat` with Syntax Highlighting (via `pygmentize`)

**Install:**
```bash
sudo dnf install python3-pygments
```

**Use:**
```bash
pygmentize -l markdown README.md | less -R
```

## Taskfile Integration

Add to your `Taskfile.yml`:

```yaml
tasks:
  # Quick view
  docs:
    desc: View README
    cmds:
      - glow README.md
  
  # View any doc
  view:
    desc: View documentation (usage: task view FILE=docs/GETTING_STARTED.md)
    vars:
      FILE: '{{.FILE | default "README.md"}}'
    cmds:
      - glow {{.FILE}}
  
  # Browse all docs
  browse:
    desc: Browse all documentation interactively
    cmds:
      - glow docs/
```

**Usage:**
```bash
# View README
task docs

# View specific file
task view FILE=docs/CONFIGURATION.md

# Browse all docs
task browse
```

## Comparison

| Tool | Pros | Cons |
|------|------|------|
| **glow** | Beautiful rendering, colors, links work | Requires installation |
| **bat** | Great syntax highlighting, fast | No markdown rendering |
| **mdless** | Good formatting, Ruby-based | Requires gem |
| **less** | Always available | No rendering |
| **cat** | Simple, available | No paging |

## My Recommendation

For your air-gapped environment with RHEL/Rocky:

1. **Best:** Install `glow` - it's in EPEL/standard repos
2. **Good:** Use `bat` - also in standard repos
3. **Fallback:** Use `less -R` - always available

## Example Taskfile.yml Section

```yaml
# Documentation tasks
tasks:
  docs:
    desc: View documentation
    cmds:
      - task: docs:readme
  
  docs:readme:
    desc: View README
    cmds:
      - glow README.md
  
  docs:getting-started:
    desc: View Getting Started guide
    cmds:
      - glow docs/GETTING_STARTED.md
  
  docs:config:
    desc: View Configuration reference
    cmds:
      - glow docs/CONFIGURATION.md
  
  docs:taskfiles:
    desc: View Taskfile documentation
    cmds:
      - glow docs/TASKFILES.md
  
  docs:troubleshoot:
    desc: View Troubleshooting guide
    cmds:
      - glow docs/TROUBLESHOOTING.md
  
  docs:all:
    desc: Browse all documentation
    cmds:
      - glow docs/
```

Then you can run:
```bash
task docs                    # View README
task docs:getting-started    # View getting started
task docs:all               # Browse all docs
```

## Install Glow in Container

Add to your container image (Dockerfile or build script):

```dockerfile
# For RHEL/Rocky-based container
RUN dnf install -y epel-release && \
    dnf install -y glow

# Or via binary
RUN curl -L https://github.com/charmbracelet/glow/releases/download/v1.5.1/glow_1.5.1_linux_x86_64.tar.gz | \
    tar xz -C /usr/local/bin glow
```

Or in your container prep task:

```yaml
prep-onboarder-container:
  desc: Prepare onboarder container with tools
  cmds:
    - dnf install -y glow
```
