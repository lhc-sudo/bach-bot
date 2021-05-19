import json
import re
import praw
from youtube_search import YoutubeSearch

reddit = praw.Reddit('BACHBOT', user_agent='Bach-Bot')  # PRAW init
sub_list = ['bach', 'baroque', 'classicalmusic']  # subs to scan

with open('/home/pi/redditBot/replied.json', 'r') as f:
    read_posts = json.load(f)
    f.close()

with open('/home/pi/redditBot/opted_out.json', 'r') as o:
    opted_out = json.load(o)
    o.close()

start_len = len(read_posts)
start_opts = len(opted_out)


def text_search(content1, content2, post_id):  # finds the BWV number in comments/posts
    BWV = re.findall(r'BWV *(\d{1,4}[a-z]?)', str(content1) + ' ' + str(content2), re.IGNORECASE)
    links = re.findall(r'[0-9A-Za-z_-]{10}[048AEIMQUYcgkosw]', str(content1) + ' ' + str(content2))
    for i in range(len(BWV)):
        BWV[i] = 'BWV ' + BWV[i]
    BWV = list(dict.fromkeys(BWV))  # removes duplicates from list by converting to dict and back
    if BWV:
        return {'id': post_id, 'BWV': BWV, 'links': links}


def yt_search(queries):  # searches on Youtube, and say thanks to u/gerubach for the videos
    results = [YoutubeSearch('"' + query + '"' + ' gerubach', max_results=1).to_json() for query in queries]
    return [json.loads(str(result)) for result in results]


def obj_reply(r_object, BWV):  # replies to comments given a comment/post object and a BWV number
    yt_results = yt_search(BWV['BWV'])
    yt_to_pop = []
    BWV_to_pop = []
    for i in range(len(yt_results)):
        try:
            if '/watch?v=' + BWV['links'][i] in yt_results[i]['videos'][0]['url_suffix']:
                yt_to_pop.append(i)
                BWV_to_pop.append(i)  # if OP already linked the same recording, don't reply with another link
        except IndexError:
            break
    for i in yt_to_pop:
        yt_results.pop(i)
    for i in BWV_to_pop:  # sooo many for loops
        BWV['BWV'].pop(i)
    message = ''
    if len(BWV['BWV']) > 0:
        for i in range(len(BWV['BWV'])):
            message += f'Here is your recording of {BWV["BWV"][i]}:\n\n[{yt_results[i]["videos"][0]["title"]}](https://youtube.com{yt_results[i]["videos"][0]["url_suffix"]})\n\n'
        message += '---\n\n^(Beep Boop. I\'m a bot - here\'s my) ^[source](https://github.com/lhc-sudo/bach-bot). ^(Summon me with u/Reddit-Bach-Bot.)\n\n'
        message += '^(To opt out of replies to posts and comments, reply to this comment with "!optout".)'
        r_object.reply(message)


inbox = reddit.inbox
for mention in inbox.mentions(limit=25):  # checks for mentions
    parent_id = mention.context.split('/')[4]  # splicing the link find the ID is painful
    text_out = text_search(mention.body, '', parent_id + '/' + mention.id)
    parent_submission = reddit.submission(parent_id)
    try:
        parent_out = text_search(parent_submission.title, parent_submission.body, parent_submission.id)
    except AttributeError:  # if the submission has no body, PRAW will return an AttributeError, so pass an empty string
        parent_out = text_search(parent_submission.title, '', parent_submission.id)
    if parent_id not in [post_id['id'] for post_id in read_posts]:  # once again check if replied
        if text_out is not None:
            obj_reply(mention, text_out)
            read_posts.append(text_out['BWV'])
        if parent_out is not None:
            obj_reply(mention, parent_out)
            read_posts.append(parent_out['BWV'])
for reply in inbox.comment_replies():  # checks for opt-outs
    if reply.body == "!optout" and reply.author.name not in opted_out:
        opted_out.append(reply.author.name)
for sub in sub_list:  # scans subs specified
    for submission in reddit.subreddit(sub).new(limit=25):
        comments = submission.comments
        comments.replace_more(limit=0)
        post_BWV = text_search(submission.title, submission.selftext, submission.id)  # searches for BWVs in posts
        try:
            author = submission.author.name.lower()
        except AttributeError:
            continue
        if post_BWV is not None and submission.id not in [post_id['id'] for post_id in read_posts] and author not in opted_out:  # apologies for the chain of ands...
            read_posts.append(post_BWV)  # hasn't been replied to
            obj_reply(submission, post_BWV)
        for comment in comments.list():  # searches comments
            comment_BWV = text_search(comment.body, '', comment.id)
            combined_id = submission.id + '/' + comment.id
            try:
                author = comment.author.name.lower()
            except AttributeError:
                continue
            if comment_BWV is not None and combined_id not in [post_id['id'] for post_id in read_posts] and author not in opted_out:
                read_posts.append({'id': submission.id + '/' + comment.id, 'BWV': comment_BWV['BWV']})
                obj_reply(comment, comment_BWV)  # checks if unreplied and not opted-out

print('Done. New replies:' + str(len(read_posts) - start_len))  # for confirmation during debugs
print('      New optouts:' + str(len(opted_out) - start_opts))

with open('/home/pi/redditBot/replied.json', 'w') as f:
    json.dump(read_posts, f, indent=4)
    f.close()

with open('/home/pi/redditBot/opted_out.json', 'w') as o:
    json.dump(opted_out, o, indent=4)
    o.close()
