![Tracker](http://i.imgur.com/2e7KpW7.jpg)
# zappa-bittorrent-tracker [![Build Status](https://travis-ci.org/Miserlou/zappa-bittorrent-tracker.svg)](https://travis-ci.org/Miserlou/zappa-bittorrent-tracker) [![Slack](https://img.shields.io/badge/chat-slack-ff69b4.svg)](https://slack.zappa.io/)

An experimental server-less BitTorrent tracker with no permanent web server and no permanent database server.

See an [example here](https://tracker.zappa.io/)!
(Note that this example should be considered unstable, as I might make changes and wipe the DB from time to time for dev reasons. If you'd like to use this tracker for a real torrent, let me know so I can set up dev and production services.)

Powered by [Zappa](https://github.com/Miserlou/Zappa), with Amazon DynamoDB or S3 as a datastore.

## Installation

Clone, virtualenv, requirements.txt. You know the drill.

Next, create a [DynamoDB table](https://console.aws.amazon.com/dynamodb/home?region=us-east-1#).

Then open up `track.py` and edit your configuration. You can set `DATASTORE` to either `S3` or `DynamoDB`, depending on which backend you want to use.

Run locally with `run.sh`, and test local announces with `announce.sh`.

Finally, to deploy, `zappa init`, `zappa deploy`, (optionally) `zappa certify`.

And you're done! You now a have a completely server-less, no-ops, low-cost, infinately scalable BitTorrent tracker!

### Purging Expired Peers

To make sure that peers who don't gracefully close their connections are purged, add this to your `zappa_settings.json`:

```javascript
{
    "production": {
       ...
       "events": [{
           "function": "track.purge_expired_peers",
           "expression": "rate(30 minutes)"
       }],
       ...
    }
}
```

And then `zappa schedule` to schedule the purge as a recurring function.

### Performance

With the training wheels taken off your AWS account, you should be able to handle 5,000 simultaneous connections per second, so with a 30-minute announce interval, this set-up should be able to handle 9,000,000 peers out of the box. With a multi-region deployment and a larger announce window, this should be able to scale to 100,000,000+ peers without much difficulty.

DynamoDB is the most expensive component of this. S3 should be far, far, far cheaper to use, but may have race problems in the peer tracking for high-traffic torrents.

### A Note on Software Freedom

DynamoDB is non-Free software. With Riak, OpenWhisk and Nginx (or the upcoming OpenWhisk API Gateway product), it should be possible to run this as part of an entirely Free Software server-less stack.

## License

Rich Jones 2016. MIT License.
