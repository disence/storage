import re
from storage.ssh import SSHSession

WWN_REGEX = re.compile('[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}'
                       , re.I)


class BrocadeSwitch(SSHSession):
    """
    Establish SSH Connection to Brocade FC Switch which can be used to run commands against it.

    Provide commonly used commands as methods and also command method to add more functionality
    """
    @staticmethod
    def fidify_command(cmd, fid):
        """
        If fid, return command that can run in given fid. Otherwise return as it is
        """
        if fid:
            return 'fosexec --fid %s -cmd "%s" ' % (fid, cmd)
        else:
            return cmd

    def isDirectorClass(self, switch_type):
        """
        Use SwitchType from switchShow command output.
        """
        DIRECTOR_CLASS_TYPES = ['42', '62', '77', '120', '121']

        if switch_type.split('.')[0] in DIRECTOR_CLASS_TYPES:
            return True
        else:
            return False

    def aliShow(self, pattern='*', fid=None):
        """
        Returns dictionary with alias name as key and it's members as values. Default pattern '*' will return all
        aliases
        """
        aliases = {}
        cmd = self.fidify_command('aliShow %s' % pattern, fid)
        output, error = self.command(cmd)

        if output and not re.search('does not exist', " ".join(output), re.IGNORECASE):
            alias_regex = re.compile('alias:(.*)')

            key = None
            values = []

            for line in output:
                line = line.strip()
                if alias_regex.search(line):
                    key = alias_regex.search(line).group(1).strip()
                    values = []
                elif WWN_REGEX.search(line):
                    values = values + WWN_REGEX.findall(line)

                if key:
                    aliases[key] = list(set(values))

        return aliases

    def fabricShow(self, membership=False, chassis=False, fid=None):
        """
        Returns fabricshow output with each switch as dictionary
        """
        fabric = {}
        cmd = 'fabricShow'

        if membership and chassis:
            pass # Defaults to fabricShow as both arguments can't be True
        elif membership:
            cmd = 'fabricShow -membership'
        elif chassis:
            cmd = 'fabricShow -chassis'

        cmd = self.fidify_command(cmd, fid)

        output, error = self.command(cmd)

        if output:
            for line in output:
                line = line.strip()
                if re.match(r'^\d+:', line):
                    values = line.split()
                    key = values.pop(0).replace(':','')
                    fabric[key] = values

        return fabric

    def switchName(self, fid=None):
        """
        Returns Switch Name.
        """
        cmd = self.fidify_command('switchName', fid)
        output, error = self.command(cmd)
        if output:
            return "".join(output).strip()

    def switchShow(self, fid=None):
        """
        Returns Switch Show in a dictionary format
        """
        cmd = self.fidify_command('switchShow', fid)
        output, error = self.command(cmd)

        dct = {}

        if output:
            #First Get Key Values
            for line in output:
                line = line.strip()
                if re.match(r'^[a-zA-z\s]+:', line):
                    key, value =  line.split(':',1)
                    dct[key] = value.strip()

            #Get All Ports
            concatenated_output = "".join(output)
            if re.search('===+', concatenated_output ):
                port_info =  re.search('===+((.|\n)*)', concatenated_output ).groups(1)[0]
                port_info_lines = port_info.strip().split('\n')

                ports = []
                for line in port_info_lines:
                    ports.append(line)
                dct['ports'] = ports
        #a = dct['ports'][0]
        #print re.split('\s*',a)
        return dct

    def version(self):
        """
        Returns dictionary with version information.
        FID not required here
        """
        dct = {}
        output, error = self.command('version')
        #print output
        for line in output:
            line = line.strip()
            if re.split('\W+ ', line) and len(re.split('\W+ ', line))==2:
                key, value = re.split('\W+ ', line)
                dct[key] = value
        return dct

    def zoneShow(self, pattern='*', fid=None):
        """
        Returns dictionary with alias name as key and it's members as values

        Pattern:'*' will return all aliases.
        """
        zones = {}
        cmd = self.fidify_command('zoneShow %s' % pattern, fid)

        output, error = self.command(cmd)

        if output and not re.search('does not exist', " ".join(output), re.IGNORECASE):
            zone_regex = re.compile('zone:(.*)')

            key = None
            values = []

            for line in output:
                line = line.strip()
                if zone_regex.search(line):
                    key = zone_regex.search(line).group(1).strip()
                    values = []
                else:
                    items = [x.strip() for x in line.split(';') if x]
                    if items:
                        values = values + items
                if key:
                    zones[key] = list(set(values))

        return zones

    def is_wwn_on_fabric(self, wwn, fid=None):
        """
        Check if given WWN (WWNN or WWPN) exists on fabric.
        Return True if exists, otherwise False
        """
        cmd = self.fidify_command('nodefind %s' % wwn, fid)
        output, error = self.command(cmd)

        if output and re.search(wwn,  " ".join(output), re.IGNORECASE):
            return True
        else:
            return False

    def wwn_alias_map(self, fid=None):
        """
        Return dictionary with wwn as key and aliases as values.
        """
        aliases = self.aliShow(fid=fid)

        map = dict()

        for alias, wwpns in aliases.items():
            for wwpn in wwpns:
                if wwpn not in map:
                    map[wwpn] = [alias]
                else:
                    if alias not in map[wwpn]:
                        map[wwpn].append(alias)

        return map

    def get_alias_zones(self, alias, fid=None):
        """
        Return a list of zones alias is part of.
        """
        zones = self.zoneShow(fid=fid)
        alias_zones = []

        for zone, aliases in zones.items():
            if alias in aliases:
                alias_zones.append(zone)

        return alias_zones

    def get_wwn_aliases(self, wwn, fid=None):
        """
        Return a list of Aliases for given wwn
        """
        map = self.wwn_alias_map(fid)

        if wwn.lower() in map:
            return map[wwn.lower()]
        elif wwn.upper() in map:
            return map[wwn.upper()]
        else:
            return []

    def get_current_active_config_name(self, fid=None ):
        """
        Return current active zone configuration name
        """
        cmd = self.fidify_command('cfgactvshow', fid)
        output, error = self.command(cmd)
        CONFIG_REGEX = re.compile('cfg:(.*)\n')

        if output:
            output = "".join(output)
            if CONFIG_REGEX.search(output):
                config = CONFIG_REGEX.search(output).groups()[0]
                return config.strip()
