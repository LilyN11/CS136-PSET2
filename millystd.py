#!/usr/bin/python

# This is a dummy peer that just illustrates the available information your peers 
# have available.

# You'll want to copy this file to AgentNameXXX.py for various versions of XXX,
# probably get rid of the silly logging messages, and then add more logic.

import random
import logging
import numpy as np

from messages import Upload, Request
from util import even_split
from peer import Peer

class MillyStd(Peer):
    def post_init(self):
        print(("post_init(): %s here!" % self.id))
        self.optimistic = "None"
    
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
        random.shuffle(needed_pieces)

        count_pieces = np.zeros(self.conf.num_pieces)
        for peer in peers:
            intersect = np_set.intersection(peer.available_pieces)
            if bool(intersect):
                count_pieces[np.array(list(intersect))] +=1

        needed_pieces.sort(key=lambda piece: int(count_pieces[piece]))

        # Sort peers by id.  This is probably not a useful sort, but other 
        # sorts might be useful
        if len(history.uploads) == 0:
            unblocked = []
        else:
            unblocked = list(np.unique([upload.to_id for upload in history.uploads[history.last_round()]]))

        def rank(p):
            if p.id in unblocked:
                return self.conf.num_pieces + len(p.available_pieces)
            else:
                return len(p.available_pieces)

        peers.sort(key=rank, reverse=True)
        
        # request all available pieces from all peers!
        # (up to self.max_requests from each)

        early = (sum(self.pieces) < self.conf.blocks_per_piece)

        for peer in peers:
            av_set = set(peer.available_pieces)
            isect = av_set.intersection(np_set)
            n = min(self.max_requests, len(isect))
            # More symmetry breaking -- ask for random pieces.
            # This would be the place to try fancier piece-requesting strategies
            # to avoid getting the same thing from multiple peers at a time.
            if isect is None:
                pass
            elif early and peer not in unblocked:
                piece_choices = random.sample(sorted(isect), n)
            else:
                piece_choices = sorted(isect, key=lambda piece: needed_pieces.index(piece))[:n]

            for piece_id in piece_choices:
                # aha! The peer has this piece! Request it.
                # which part of the piece do we need next?
                # (must get the next-needed blocks in order)
                start_block = self.pieces[piece_id]
                r = Request(self.id, peer.id, piece_id, start_block)
                requests.append(r)

                needed_pieces.remove(piece_id)
                needed_pieces.append(piece_id)

        return requests

    def uploads(self, requests, peers, history):
        """
        requests -- a list of the requests for this peer for this round
        peers -- available info about all the peers
        history -- history for all previous rounds

        returns: list of Upload objects.

        In each round, this will be called after requests().
        """
        m = 4

        round = history.current_round()
        logging.debug("%s again.  It's round %d." % (
            self.id, round))
        # One could look at other stuff in the history too here.
        # For example, history.downloads[round-1] (if round != 0, of course)
        # has a list of Download objects for each Download to this peer in
        # the previous round.

        if len(requests) == 0:
            logging.debug("No one wants my pieces!")
            chosen = []
            bws = []
        else:
            logging.debug("Still here: uploading to peers")

            interested = list(np.unique([request.requester_id for request in requests]))

            generosity = {peer.id : 0 for peer in peers}
            hist = []
            if round > 0:
                hist += history.downloads[round-1]
            if round > 1:
                hist += history.downloads[round-2]
            for download in hist:
                if download.to_id == self.id:
                    generosity[download.from_id] += download.blocks

            chosen = sorted(interested, key = lambda peer: generosity[peer], reverse=True)[:m-1]
            unchosen = [peer for peer in interested if peer not in chosen]

            if round % 3 == 0:
                unchosen = [peer for peer in interested if peer not in chosen]
                if len(unchosen) > 0:
                    self.optimistic = random.choice(unchosen)
            
            if self.optimistic not in chosen:
                chosen.append(self.optimistic)

            # Evenly "split" my upload bandwidth among the one chosen requester
            bws = even_split(self.up_bw, len(chosen))

        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]
            
        return uploads
