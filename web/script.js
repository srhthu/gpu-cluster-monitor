var interval_id;
var cluster_data;

$(document).ready(function(){
    get_data();
    interval_id = window.setInterval(get_data, 3000);
    $("#update").click(get_data)
    $("#auto-update").click(function(){
        interval_id = window.setInterval(get_data, 3000);
    })
    $("#stop-update").click(function(){
        window.clearInterval(interval_id);
    })
    remove_blank(document.getElementById("head-line"));

    // listen scroll to make nav bar at top.
    window.addEventListener('scroll', onScroll);
})

function remove_blank(oEelement){
    for(var i=0;i<oEelement.childNodes.length;i++){
        var node=oEelement.childNodes[i];
        if(node.nodeType==3 && !/\S/.test(node.nodeValue)){
            node.parentNode.removeChild(node)
        }
    }
}


function get_data(){
    $.ajax({
        url:"/get-status",
        type:"GET",
        contentType: "application/json",
        success: create_page,
        timeout:2000
    })
}

function create_page(data){
    // teamup link
    // $("#teamup_link").attr('href', "https://teamup.com/" + data.teamup_id);

    // add the calendar date in the head line
    cluster_data = data;
    
    var content = $("#content-status").empty();
    for (var i=0; i<data.Nodes.length; i++) {
        var n_data = data.Nodes[i];
        var node = $("#content-status-sample .node-line").clone();
        // node information
        node.find(".node-name").text(n_data.hostname);
        node.find(".node-status").attr("data-status", n_data.status);
        node.find('.node-version').text(n_data.version);
        if (n_data.ips) {
            ips = n_data.ips;
            var ip_str = '';
            for (j = 0; j< ips.length; j++) {
                ip_str = ip_str + ips[j][1] + '(' + ips[j][0] + ')&nbsp;&nbsp;&nbsp;&nbsp;';
            }
            node.find('.node-ip').html(ip_str);
        }

        // fill gpu status
        var gpu_area = node.find(".gpu-list").empty();
        for (j=0; j<n_data.gpus.length; j++) {
            var gpu_data = n_data.gpus[j];
            var gpu_line = $("<div></div>").addClass("gpu-line");
            gpu_line.append($("<div></div>").addClass("colum gpu-idx").text(gpu_data.index))
            
            //memory
            gpu_line.append($("<div></div>").addClass("colum memory").text(gpu_data.use_mem + "/" + gpu_data.tot_mem));
            var mem_per = gpu_data.use_mem / gpu_data.tot_mem * 100;
            gpu_line.find(".colum.memory").css("background", `linear-gradient(to right, #99CC66 ${mem_per}%, white ${mem_per}%, white)`);
            gpu_line.append($("<div></div>").addClass("colum utilize").text(gpu_data.utilize + " %"));
            
            // add current user information
            gpu_line.append($("<div></div>").addClass("colum users").text(' '));
            if (gpu_data.users.length==0) {
                gpu_line.find(".colum.users").html("&nbsp;")
            }
            else {
                html_str = ''
                for (ui=0; ui<gpu_data.users.length; ui++){
                    var u_info = gpu_data.users[ui];
                    html_str = html_str + u_info.username + " "
                }
                gpu_line.find(".colum.users").html('<div>' + html_str + '</div>')
            }
            
            // update 2022.7.25
            var wrap_line = $("<div></div>");
            wrap_line.append(gpu_line);
            gpu_area.append(wrap_line);
        }

        content.append(node);

    }
}


function onScroll(){
    var scrollTop = document.body.scrollTop || document.documentElement.scrollTop;
    if (scrollTop <= 180) {
        $("#head-line").removeClass();
        // console.log('scroll ' + String(scrollTop));
    }
    else {
        $("#head-line").removeClass();
        $("#head-line").addClass("nav-at-top");
        // console.log('scroll ' + String(scrollTop));
    }
}