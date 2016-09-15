# zappa-bittorrent-tracker [![Build Status](https://travis-ci.org/Miserlou/zappa-bittorrent-tracker.svg)](https://travis-ci.org/Miserlou/zappa-bittorrent-tracker) [![Slack](https://img.shields.io/badge/chat-slack-ff69b4.svg)](https://slack.zappa.io/)

An experimental server-less BitTorrent tracker with no webserver and a managed database server.

Powered by [Zappa](https://github.com/Miserlou/Zappa), with Amazon DynamoDB (or later S3) as a database.

## Installation

Clone, virtualenv, requirements.txt. You know the drill.

Next, create a [DynamoDB table](https://console.aws.amazon.com/dynamodb/home?region=us-east-1#).

Then open up `track.py` and edit your configuration.

Run locally with `run.sh`, and test local announces with `announce.sh`.

Finally, to deploy, `zappa init`, `zappa deploy`, (optionally) `zappa certify`.

And you're done! You now a have a completely server-less, no-ops, low-cost, infinately scalable BitTorrent tracker!

#### Caveats

DynamoDB is non-Free software. S3 is also non-Free, but there are S3-compatible Free alternatives. The first version of this program will use DynamoDB, and hopefully later versions will use S3 as an alternative. Ideally, it will be possible to one day use this software as part of a completely _Free as in Freedom_ server-less stack.
