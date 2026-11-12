# Data

Three public-domain novels from [Project Gutenberg](https://www.gutenberg.org/), with the Project Gutenberg
header and licence footer removed (so these files are plain public-domain text, not Project Gutenberg eBooks):

| File | Book | Gutenberg # | Role in this repo |
|---|---|---|---|
| `pride_and_prejudice.txt` | Jane Austen, *Pride and Prejudice* | 1342 | trains the language model (letter n-grams, word list); never encrypted |
| `sherlock_holmes.txt` | Arthur Conan Doyle, *The Adventures of Sherlock Holmes* | 1661 | cut into three disjoint regions: fit, steering and probe ciphers |
| `frankenstein.txt` | Mary Shelley, *Frankenstein* | 84 | the sealed held-out ciphers (different author, era and vocabulary) |

Using a different book for each role is what lets a held-out number mean "unseen text", not "unseen windows of
the same text".
