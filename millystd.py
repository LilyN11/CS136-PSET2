#!/usr/bin/python

# This is a dummy peer that just illustrates the available information your peers 
# have available.

# You'll want to copy this file to AgentNameXXX.py for various versions of XXX,
# probably get rid of the silly logging messages, and then add more logic.

import random
import logging

from messages import Upload, Request
from util import even_split
from peer import Peer

class MillyStd(Peer):
    def post_init(self):
        print(("post_init(): %s here!" % self.id))
        self.dummy_state = dict()
        self.download_rates = dict() #ADDED  dictionary
    
    def requests(self, peers, history):
        """
        peers: available info about the peers (who has what pieces)
        history: what's happened so far as far as this peer can see

        returns: a list of Request() objects

        This will be called after update_pieces() with the most recent state.
        """
        needed = lambda i: self.pieces[i] < self.conf.blocks_per_piece
        needed_pieces = list(filter(needed, list(range(len(self.pieces)))))
        np_set = set(needed_pieces)  # sets support fast intersection ops.

        logging.debug("%s here: still need pieces %s" % (
            self.id, needed_pieces))

        logging.debug("%s still here. Here are some peers:" % self.id)
        for p in peers:
            logging.debug("id: %s, available pieces: %s" % (p.id, p.available_pieces))

        logging.debug("And look, I have my entire history available too:")
        logging.debug("look at the AgentHistory class in history.py for details")
        logging.debug(str(history))

        requests = []   # We'll put all the things we want here
        # Symmetry breaking is good...
        # random.shuffle(needed_pieces)
        
        # Sort peers by id.  This is probably not a useful sort, but other 
        # sorts might be useful
        # peers.sort(key=lambda p: p.id)
        #ADDED count how many times each piece appears
        count_pieces = {piece: 0 for piece in np_set}
        for peer in peers:
            for piece in peer.available_pieces:
                if piece in count_pieces:
                    count_pieces[piece] += 1

        #ADDED sort rarity
        needed_pieces.sort(key=lambda piece: count_pieces[piece])

        # ADDED request rarest pieces
        # (up to self.max_requests from each)
        for peer in peers:
            av_set = set(peer.available_pieces)
            isect = av_set.intersection(np_set)
            n = min(self.max_requests, len(isect))
            #ADDED
            for piece_id in sorted(isect, key=lambda piece: count_pieces[piece])[:n]:
                start_block = self.pieces[piece_id]
                r = Request(self.id, peer.id, piece_id, start_block)
                requests.append(r)

        return requests

    def uploads(self, requests, peers, history):
        """
        requests -- a list of the requests for this peer for this round
        peers -- available info about all the peers
        history -- history for all previous rounds

        returns: list of Upload objects.

        In each round, this will be called after requests().
        """

        round = history.current_round()
        logging.debug("%s again.  It's round %d." % (
            self.id, round))
        if round > 0:
            for download in history.downloads[round-1]:
                peer_id = download.from_id
                amount_downloaded = download.blocks
                if peer_id not in self.download_rates:
                     self.download_rates[peer_id] = []
                rate = amount_downloaded / 20  # ADDED each round 20 seconds?
                self.download_rates[peer_id].append(rate)
            
        # One could look at other stuff in the history too here.
        # For example, history.downloads[round-1] (if round != 0, of course)
        # has a list of Download objects for each Download to this peer in
        # the previous round.

        #ADDED CALC DOWNLOAD RATE
        def calc_download(peer_id):
            if peer_id not in self.download_rates or not self.download_rates[peer_id]:
                return 0
            return sum(self.download_rates[peer_id]) / len(self.download_rates[peer_id])

        interested_peers = [r.requester_id for r in requests].sort(key=calc_download, reverse=True)[:3]
        blocked_peers = [r.requester_id for r in requests if calc_download(r.requester_id) = 0]
        
        if round % 3 == 0:
            if blocked_peers:
                unblock_random = random.choice(blocked_peers)
                interested_peers.append(unblock_random)

        if len(requests) == 0:
            logging.debug("No one wants my pieces!")
            # chosen = []
            bws = []
        else:
            #ADDED allocate bandwith among top requesters
            bws = even_split(self.up_bw, len(4)) 
        if bws is None:
            bws = []
        if interested_peers is None:
            interested_peers = []
        print("DEBUG: interested_peers =", interested_peers)
        print("DEBUG: bws =", bws)
        # create actual uploads out of the list of requester ids and bandwidths
        uploads = [Upload(self.id, requester_id, bw)
                   for (requester_id, bw) in zip(interested_peers, bws)]
        print(uploads)    
        return uploads
