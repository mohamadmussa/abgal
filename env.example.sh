# Copy this file to env.local.sh next to it. Everything matching *.local.* is
# in .gitignore, so your copy can never reach a commit.
#
# Only values that belong to your machine go here. Anything that belongs to
# the project belongs in devices.conf or app.conf instead.

# The app under test. Read by install-app.sh and fetch-app.sh.
# export ABGAL_PACKAGE=com.example.app

# Where the package files live. Defaults to apk/ inside the repository.
# export ABGAL_APP_DIR=/path/to/packages

# Graphics. "software" runs on any machine, "host" uses the graphics card
# and is worth measuring before you keep it.
# export ABGAL_GPU=host

# System language of the guest at start.
# export ABGAL_LOCALE=ar-SA

# Temperature watch. Warning threshold and abort value in degrees Celsius.
# export ABGAL_TEMP_WARN=88
# export ABGAL_TEMP_STOP=96

# Turn the watch off on a machine whose sensors cannot be read.
# export ABGAL_TEMP_WATCH=0
