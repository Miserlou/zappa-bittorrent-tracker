Notes
===========

Plan of attack:

    * Proxy existing Torrent connections
    * Run Hidden Service
    * Announce to Tracker Using Hidden Service Address
        - Can an announce be a URL?
            - Does it need to?
                No, can be DNS name (.onion)
        - Fuck a UDP tracker. :[
            - http://tracker.opentrackr.org:1337/announce works
            - OnionCat won't work outside the network: https://www.whonix.org/wiki/OnionCat
                - Zappa tracker!
                    - S3 Database! SQS trimming
        - Can an announce be a .onion URL?
            - Will this require tracker modification?
                - Fuck it, lets invent our own Tracker:
                    - https://github.com/Miserlou/zappa-bittorrent-tracker
        - Fuck a DHT. :[
            - UDP only. Boo.
                - Maybe doable inside the network?
        - PEX
            - Should work? http://www.bittorrent.org/beps/bep_0011.html
    * Properly Handle Hidden Service Connections
    * Bundle Tor
    * Bundle Control Port
    * New Skin in App, because we're fabulous
    * Package
        - OSX, Linux, Windows
    * Slack and all that