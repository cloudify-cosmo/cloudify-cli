
class MockListResponse(object):

    def __init__(self, items, _):
        self.items = items
        self.metadata = None

    def __iter__(self):
        return iter(self.items)

    def __getitem__(self, index):
        return self.items[index]

    def __len__(self):
        return len(self.items)

    def sort(self, cmp=None, key=None, reverse=False):
        return self.items.sort(cmp, key, reverse)
