---
name: python-comments
description: Docstring and inline comment rules for Python. Use when writing Python comments.
---

# Comments and Documentation Skill

Guidelines for docstrings and comments in Python. The goal is **readable code** — a developer should be able to understand the module's logic by reading the docstrings and comments without tracing through the implementation.

---

## Module docstrings

- Every `.py` file **must** have a module-level docstring.
- Describe the module's purpose in plain narrative prose.
- For modules with multiple public functions or classes, list and briefly describe them.
- For pipeline or orchestration modules, describe the steps performed.

## Function docstrings — Google style, narrative depth

- Use **Google-style** docstrings.
- **Multi-line docstrings start the text on the line after the opening `"""`**, never on the same line:

```python
# BAD — text on the same line as opening quotes
def foo():
    """Create random fold assignments for n_rows.

    Returns an array of length n_rows.
    """

# GOOD — opening quotes alone on first line, text starts on the next line
def foo():
    """
    Create random fold assignments for n_rows.

    Returns an array of length n_rows.
    """
```

- Single-line docstrings (rare — only for trivial helpers) keep everything on one line: `"""Return True if x is positive."""`
- **Never write a one-liner that restates the function name.** `def load_data` does not need `"""Load data."""`. Either write a substantive docstring or omit it.
- For any non-trivial function, the docstring must be **multi-line** and explain:
  1. **What** the function does at the domain level — not "processes data" but "stitches together a CBI price index from two sources".
  2. **How** it works — the algorithm or logic in numbered steps or narrative prose.
  3. **What** it returns — describe the structure, columns, or shape of the output.
- Include `Args:` when parameters carry domain meaning not obvious from the name (e.g., `std_ratio`, `filter_outliers`, `RSI_stop_date`).
- Include `Returns:` when the return value is a complex structure (DataFrame with specific columns, tuple, dict).
- Omit docstrings only on trivial private helpers where the name and signature are self-explanatory.

### Good vs bad examples

```python
# BAD — restates the function name, tells the reader nothing
def create_CBI_from_SSB_and_RSI(SSB_quarterly, RSI_weekly, RSI_stop_date=None):
    """Create CBI from SSB and RSI data."""

# GOOD — explains the domain logic, the stitching algorithm, and the output structure
def create_CBI_from_SSB_and_RSI(SSB_quarterly, RSI_weekly, RSI_stop_date=None):
    """
    Stitches together a CBI price index from two different price indices:
    1. Use SSB_quarterly for the period before RSI_weekly is sufficiently populated.
       This is a quarterly sampled price index from SSB, with distinct regions
       (covering all of Norway), but no count data.
    2. Use RSI_weekly for the main period, where this RSI is sufficiently populated.
       This RSI is supplied as a LORSI cube class, which contains Logarithmic
       Repeated Sales Indices (LORSI).

    Returns: DataFrame with "date" and "price" columns, plus additional information
        on how the index was created, and a "count" column representative of the
        number of transactions used to compute the index.
    """
```

### Class docstrings

- Document the class's purpose and list key instance variables with their meaning.
- Domain-specific abbreviations are acceptable in variable names when the docstring defines them (e.g., `df_MT` — DataFrame of Matched Transactions).

```python
class LORSIPartitionClass:
    """Logarithmic Repeated Sales Index for a single geographic partition.

    Computes LORSI values across date ranges and BRA (floor area) groups.
    Supports filtering, serialization, and conversion to DataFrames.

    Instance variables:
        LORSI: 3D numpy array (geo × BRA × time) of index values.
        count: 3D numpy array of transaction counts per cell.
        BRA_split: boolean array indicating which BRA groups are active.
    """
```

## Section dividers

- In longer modules (200+ lines), use docstring-style section dividers to separate logical groups:

```python
""" FUNCTIONS FOR DATA LOADING """
```

## Inline comments — narrate the reasoning

Inline comments are **mandatory** at each logical step in non-trivial functions. They narrate the domain reasoning so a reader can follow the logic without deciphering the code.

- **Comment every logical step** — not every line, but every block that does something conceptually distinct. A function with 5 logical steps should have ~5 comments.
- Explain **why this step is needed** and **what domain rule it implements**, not what the code mechanically does.
- Write in natural language: "Extract the date where the CBI data will start. This is simply the first date in the SSB data."
- Place comments on their own line above the code, not at the end of a line.

### Good vs bad examples

```python
# BAD — mechanical, tells you nothing beyond what the code says
min_date = df["date"].min()  # get min date

# GOOD — explains the domain reasoning behind the operation
# Extract the date where the CBI data will start. This is simply the first date in the SSB data.
CBI_start_date = SSB_quarterly["date"].min()
```

```python
# BAD — no comments, reader must reverse-engineer the filtering logic
df = df.dropna(subset=['grunnkrets_number', 'postcode', 'sold_date', 'location', 'BRA-i', 'price_inc_debt'])
df = df[df['price_inc_debt'] != 0]

# GOOD — explains what data quality rules are being enforced and why
# Remove transactions with missing geographic or property data — these cannot be placed in any partition.
df = df.dropna(subset=['grunnkrets_number', 'postcode', 'sold_date', 'location', 'BRA-i', 'price_inc_debt'])
# Exclude zero-price transactions, which represent non-market transfers (gifts, inheritance).
df = df[df['price_inc_debt'] != 0]
```

## Prohibited patterns

- **Never** comment out code. Delete it. Version control handles history.
- **No edit-history comments** ("added in v2", "removed old logic", "changed from X to Y").
- **No mechanical comments** that restate what the code does: `x = x + 1  # increment x`.
