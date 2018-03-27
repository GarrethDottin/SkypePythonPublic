from util.plugin import command
from util.google import get_results


@command(name='google', help='Google a query and get results.')
def google_command(chat, message, args, sender):
    if len(args) == 0:
        chat.SendMessage("Specify a query")
        return
    query = ' '.join(args)
    results, count = get_results(query, 'web')
    if count == 0:
        chat.SendMessage("No results found.")
    sb = u'First 2 results of %s for \'%s\':\n' % (str(count), query)
    temp = 1
    for title, link in results.items():
        sb += "%s. %s - %s\n" % (str(temp), title, link)
        if temp == 2:
            break
        temp += 1
    chat.SendMessage(sb)