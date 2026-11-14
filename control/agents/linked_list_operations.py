"""Deterministic linked-list operations for the versioned benchmark."""
from dataclasses import dataclass

@dataclass
class Node:
    value: int
    next: 'Node | None' = None


def build(items):
    head = None
    for value in reversed(items):
        head = Node(value, head)
    return head


def delete_first(head, target, fault=None):
    if fault == 'empty' and head is None:
        raise ValueError('空链解引用')
    if head is not None and head.value == target and fault != 'head':
        remaining = head.next
        return delete_first(remaining,target,'all') if fault=='all' else remaining
    prev, current = head, head.next if head is not None else None
    while current is not None:
        if current.value == target:
            if fault != 'tail' or current.next is not None:
                prev.next = current.next
            if fault!='all':
                return head
            current = prev.next
            continue
        prev, current = current, current.next
    return None if fault=='missing' else head


def delete_last(head, target, fault=None):
    if fault == 'empty' and head is None:
        raise ValueError('空链解引用')
    if fault == 'all':
        return delete_first(head,target,'all')
    previous, current = None, head
    match, match_previous = None, None
    while current is not None:
        if current.value==target:
            match, match_previous = current, previous
        previous, current = current, current.next
    if match is None:
        return None if fault=='missing' else head
    if match_previous is None:
        return head if fault=='head' else match.next
    if fault != 'tail' or match.next is not None:
        match_previous.next=match.next
    return head


def execute(items, target, fault=None, last=False):
    try:
        operation=delete_last if last else delete_first
        result = operation(build(items), target, fault)
        actual = []
        while result is not None:
            actual.append(result.value)
            result = result.next
        return actual
    except ValueError:
        return '运行错误：空链解引用'
