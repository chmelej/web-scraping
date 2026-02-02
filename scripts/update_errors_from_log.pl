#!/usr/bin/perl -w
# File name: filter.pl
# Date:      2026/02/02 10:59
# Author:    Jan Chmelensky <chmelej@seznam.cz>
# die "Bad command parameters\n   Usage: $0 <file>\n" if ($#ARGV < 0);

while (<>) {
    if (/Request to (http\S+)\s+failed and reached maximum retries/) {
        incr('max_retries',$1);
    } elsif (/request to (http\S+)\s+due to: Page.goto: net::ERR_CERT_COMMON_NAME_INVALID/) {
        incr('ERR_CERT_COMMON_NAME_INVALID',$1);
    } elsif (/request to (http\S+)\s+due to: Page.goto: net::ERR_SSL_VERSION_OR_CIPHER_MISMATCH/) {
        incr('ERR_SSL_VERSION_OR_CIPHER_MISMATCH',$1);
    } elsif (/request to (http\S+)\s+due to: Page.goto: net::ERR_NAME_NOT_RESOLVED/) {
        incr('ERR_NAME_NOT_RESOLVED',$1);
    } elsif (/request to (http\S+)\s+due to: Page.goto: net::ERR_SSL_PROTOCOL_ERROR/) {
        incr('ERR_SSL_PROTOCOL_ERROR',$1);
    } elsif (/request to (http\S+)\s+due to: Page.goto: net::ERR_CONNECTION_RESET/) {
        incr('ERR_CONNECTION_RESET',$1);
    } elsif (/request to (http\S+)\s+due to: Page.goto: net::ERR_CERT_DATE_INVALID/) {
        incr('ERR_CERT_DATE_INVALID',$1);
    } elsif (/Timeout \d+ms exceeded...Call log:..  - navigating to "(\S+)"/) {
        incr('TimeoutExceeded',$1);
    }

}

sub incr {
    $error = shift;
    $url = shift;
    #$url =~ s|/$||;     # zahod lomitko
    print "UPDATE table SET err='$error' WHERE url = '$url';\n";
}
