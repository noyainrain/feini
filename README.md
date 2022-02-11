# Open Feini

Virtual pet chatbot and relaxing text game experiment.

You can give it a try at [feini.chat](https://feini.chat/).

## System requirements

The following software must be installed on your system:

* Python >= 3.9
* Redis >= 6.0

Open Feini should work on any [POSIX](https://en.wikipedia.org/wiki/POSIX) system.

## Installing dependencies

To install all dependencies, run:

```sh
make deps
```

## Running Open Feini

To run Open Feini, use:

```sh
python3 -m feini
```

The configuration file `fe.ini` is used, if present. See `feini/res/default.ini` for documentation.

## Messenger support

Open Feini currently supports Telegram. Support for further messengers is planned.

## Contributors

* Sven Pfaller &lt;sven AT inrain.org>

Copyright (C) 2022 Open Feini contributors
