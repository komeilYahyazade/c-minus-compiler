# C-minus Compiler

## Overview

The **C-minus Compiler** is a Python-based, one-pass compiler for a simplified version of the C programming language, **C-minus**. The project is divided into four main components, each developed through successive programming assignments:

1. **Scanner (Lexical Analyzer)**
2. **Parser**
3. **Intermediate Code Generator (Part I)**
4. **Semantic Analyzer and Intermediate Code Generator (Part II)**

Each phase builds a functional compiler component that integrates with the others to form a complete compilation pipeline.

## Features

- **Scanner**: Tokenizes C-minus source code, identifying keywords, identifiers, literals, operators, and punctuation.
- **Parser**: Constructs a syntax tree from the token stream, validating the program's structure.
- **Intermediate Code Generator**: Translates the syntax tree into an intermediate representation for further processing.
- **Semantic Analyzer**: Performs type checking and scope resolution, ensuring semantic correctness of the code.
