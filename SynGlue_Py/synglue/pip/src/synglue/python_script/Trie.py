# Trie
import pandas as pd
import csv
import time

class TrieNode:
    def __init__(self):
        self.children = {}
        self.is_end_of_word = False


class Trie:
    def __init__(self):
        self.root = TrieNode()
        self.hash_map = {}

    def insert(self, word):
        node = self.root
        for char in word:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        node.is_end_of_word = True

    def search(self, word):
        node = self.root
        for char in word:
            if char not in node.children:
                return False
            node = node.children[char]
        return node.is_end_of_word

    def starts_with(self, prefix):
        node = self.root
        for char in prefix:
            if char not in node.children:
                return False
            node = node.children[char]
        return True


    #  def store_all_fragments(self, prefix, smile, hmdb_id,file):
    # self, fragSmile with $ reversed, query_smile, query_frag_id, query_magnet_mapping_file
    def store_all_fragments(self, prefix, query_smile, query_frag_id, query_smile_id, file):
        node = self.root
        frag = []
        for char in prefix:
            node = node.children[char]
            frag.append(char)
        database=open(file, mode='a', newline='')
        writer = csv.writer(database)
        self.dfs(frag, node, prefix, writer, query_frag_id, query_smile, query_smile_id) # prefix - fragSmile with $ reversed
        database.close()

    def dfs(self, frag, node, prefix, writer,query_frag_id, query_smile, query_smile_id):
        if node.is_end_of_word:
            writer.writerow([prefix[::-1][:-1], "".join(frag[::-1][:-1]), query_frag_id , self.hash_map["".join(frag[::-1][:-1])], query_smile, query_smile_id])
        if not node.children:
            return
        for child in node.children:
            frag.append(child)
            self.dfs(frag, node.children[child], prefix, writer, query_frag_id, query_smile, query_smile_id)
            frag.pop()
        return
    
    
    # functiona for correct serialisation and deserialisation
    def __getstate__(self):
        # Return the state of the object for pickling
        return self.root

    def __setstate__(self, state):
        # Restore the state of the object from unpickling
        self.root = state