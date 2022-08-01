## @file
# Check CODEOWNERS, REVIEWERS, and Maintainers.txt files.
#
# Copyright (c) 2022, Intel Corporation. All rights reserved.<BR>
# SPDX-License-Identifier: BSD-2-Clause-Patent
##

'''
CheckCodeOwnersMaintainers
'''
import os
import sys
import json
import GetMaintainer
from   cached_property import cached_property
from   codeowners      import CodeOwners
from   git             import Git

class CheckCodeOwnersMaintainers (object):
    def __init__ (self):
        self._Hub                = None
        self._HubPullRequest     = None
        self._EventContext       = None
        self._EmailToLogin       = {}
        self._InputToken         = os.environ.get('INPUT_TOKEN')
        self._EventPath          = os.environ.get('GITHUB_EVENT_PATH')
        self._EventName          = os.environ.get('GITHUB_EVENT_NAME')
        self._InputReviewersPath = os.environ.get('INPUT_REVIEWERS_PATH')
        self._repo               = None

    @cached_property
    def EventContext (self):
        # Verify that the event is a pull request
        if self._EventName not in ['pull_request', 'pull_request_target']:
            sys.exit(f"ERROR: Event({self._EventName}) must be 'pull_request' and 'pull_request_target'.")
        # Parse JSON file that contains the GitHub PR event context
        print(f"Parse JSON file GITHUB_EVENT_PATH:{self._EventPath}")
        try:
            self._EventContext = json.load(open(self._EventPath))
        except:
            sys.exit(f"ERROR: Unable to parse JSON file GITHUB_EVENT_PATH:{self._EventPath}")

        # Verify that all the JSON fields required to complete this action are present
        for Key in ['action', 'repository', 'pull_request']:
            if Key not in self._EventContext:
                sys.exit(f"ERROR: Event context does not contain '{Key}'")
        for Key in ['full_name']:
            if Key not in self._EventContext['repository']:
                sys.exit(f"ERROR: Event repository context does not contain '{Key}'")
        for Key in ['draft', 'commits', 'base', 'head', 'number', 'user', 'assignees', 'requested_reviewers', 'requested_teams']:
            if Key not in self._EventContext['pull_request']:
                sys.exit(f"ERROR: Event pull request context does not contain '{Key}'")
        if self._EventContext['pull_request']['draft']:
            # Exit with success if PR is a draft and do not assign reviewers
            sys.exit(0)
        for Key in ['repo', 'ref']:
            if Key not in self._EventContext['pull_request']['base']:
                sys.exit(f"ERROR: Event pull request base context does not contain '{Key}'")
        for Key in ['html_url']:
            if Key not in self._EventContext['pull_request']['base']['repo']:
                sys.exit(f"ERROR: Event pull request base repo context does not contain '{Key}'")
        for Key in ['sha']:
            if Key not in self._EventContext['pull_request']['head']:
                sys.exit(f"ERROR: Event pull request head context does not contain '{Key}'")
        for Key in ['login']:
            if Key not in self._EventContext['pull_request']['user']:
                sys.exit(f"ERROR: Event pull request user context does not contain '{Key}'")
        return self._EventContext

    @cached_property
    def EventRepository (self):
        return self.EventContext['repository']

    @cached_property
    def EventPullRequest (self):
        return self.EventContext['pull_request']

    @cached_property
    def EventCommits (self):
        return self.EventPullRequest['commits']

    @cached_property
    def EventBase (self):
        return self.EventPullRequest['base']

    @cached_property
    def EventHead (self):
        return self.EventPullRequest['head']

    @cached_property
    def Hub(self):
        # Use GitHub API to retrieve a Hub object using the input token
        print(f"Get Hub object using input token")
        try:
            self._Hub = Github (self._InputToken)
        except:
            sys.exit(f"ERROR: Unable to retrieve Hub object")
        return self._Hub

    @cached_property
    def HubPullRequest(self):
        # Use GitHub API to retrieve the pull request object
        print(f"Get HubPullRequest object for PR #{self.EventPullRequest['number']}")
        try:
            self._HubPullRequest = self.Hub.get_repo(self.EventRepository['full_name']).get_pull(self.EventPullRequest['number'])
        except:
            sys.exit(f"ERROR: Unable to retrieve PullRequest object")
        return self._HubPullRequest

    @cached_property
    def Repo(self):
        self._repo = Git('.')
        return self._repo

    def GetModifiedFiles(self, sha, commits):
        # Use git diff to determine the set of files modified by a set of commits
        print(f"Get files modified by commits in range {sha}~{commits}..{sha}")
        try:
            return self.Repo.diff(f"{sha}~{commits}..{sha}", '--name-only').split()
        except:
            sys.exit(f"ERROR: Unable to determine files modified in range {sha}~{commits}..{sha}")

    def _CodeOwnerPaths (self, BaseName, Override = ''):
        # Build prioritized list of file paths to search for a file with CODEOWNERS syntax
        return [Override, f'./{BaseName}', f'./docs/{BaseName}', f'./.github/{BaseName}']

    def _ParseCodeOwners (self, paths):
        # Search prioritized list of paths for a CODEOWNERS syntax file and parse the first file found
        for file in paths:
            if file and os.path.exists(file):
                print(f"Attempt to parse file {file}")
                try:
                    Result = CodeOwners(open(file).read())
                    print(f"Found file {file}")
                    return Result
                except:
                    continue
        # No files found in the prioritized list
        return None

    def ParseCodeownersFile (self):
        # Parse first CODEOWNERS file found in prioritized list
        return self._ParseCodeOwners (
                      self._CodeOwnerPaths('CODEOWNERS')
                      )

    def ParseReviewersFile (self):
        # Parse first REVIEWERS file found in prioritized list
        return self._ParseCodeOwners (
                      self._CodeOwnerPaths('REVIEWERS', self._InputReviewersPath)
                      )

def GetOwners(File, Sections):
    List = GetMaintainer.get_maintainers(File, Sections)
    Maintainers = []
    Reviewers = []
    for Item in List:
      if Item.startswith('M:'):
        if '[' in Item:
          Maintainers.append('@' + Item.rsplit('[')[1].rsplit(']')[0])
        else:
          Maintainers.append(Item.rsplit('<')[1].rsplit('>')[0])
      if Item.startswith('R:'):
        if '[' in Item:
          Reviewers.append('@' + Item.rsplit('[')[1].rsplit(']')[0])
        else:
          Reviewers.append(Item.rsplit('<')[1].rsplit('>')[0])
    Maintainers = list(set(Maintainers))
    Reviewers = list(set(Reviewers))
    Maintainers.sort()
    Reviewers.sort()
    return Maintainers, Reviewers

if __name__ == '__main__':
    # Initialize CheckCodeOwnersMaintainers object
    Request = CheckCodeOwnersMaintainers()
    # Parse COWEOWNERS file
    LookupCodeOwners = Request.ParseCodeownersFile()
    if LookupCodeOwners is None:
        sys.exit('ERROR: No CODEOWNERS file found')
    # Parse REVIEWERS file
    LookupReviewers  = Request.ParseReviewersFile()
    if LookupReviewers is None:
        sys.exit('ERROR: No REVIEWERS file found')
    # Parse Maintainers.txt file        
    if not os.path.exists('Maintainers.txt'):
        sys.exit('ERROR: No Maintainers.txt file found')
    Sections = GetMaintainer.parse_maintainers_file('Maintainers.txt')
    
    NoMaintainerCount      = 0
    CodeOwnerMismatchCount = 0
    ReviewerMismatchCount  = 0
    for File in Request.Repo.ls_files().split():
      Maintainers, Reviewers = GetOwners (File, Sections)
      CodeOwnersMaintainers = [x[1] for x in LookupCodeOwners.of (File)]
      CodeOwnersMaintainers.sort()
      if CodeOwnersMaintainers == [] and Maintainers == []:
          print (f"No Maintainers for File: {File}")
          NoMaintainerCount += 1
      if CodeOwnersMaintainers != Maintainers:
          print (f"Maintainer mismatch for File: {File}")
          print (f"  CODEOWNERS     : {CodeOwnersMaintainers}")
          print (f"  Maintainers.txt: {Maintainers}")
          CodeOwnerMismatchCount += 1
      CodeOwnersReviewers = [x[1] for x in LookupReviewers.of (File)]
      CodeOwnersReviewers.sort()
      if CodeOwnersReviewers != Reviewers:
          print (f"Reviewer mismatch for File: {File}")
          print (f"  REVIEWERS      : {CodeOwnersReviewers}")
          print (f"  Maintainers.txt: {Reviewers}")
          ReviewerMismatchCount += 1

    if NoMaintainerCount > 0 or CodeOwnerMismatchCount > 0 or ReviewerMismatchCount > 0:
        sys.exit(f"No Maintainers: {NoMaintainerCount}  CodeOwnerMismatch: {CodeOwnerMismatchCount}  ReviewerMismatch: {ReviewerMismatchCount}")

    print ('All files have maintainers.')    
    print ('No maintainer mismatches.')    
    print ('No reviewer mismatches.')    
